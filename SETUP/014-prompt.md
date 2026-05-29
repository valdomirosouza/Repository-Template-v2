# Prompt 014 — Security & Resilience Hardening Programme (v1.17.0)

> **Skip any file that already exists with real content.**
> This prompt is idempotent — re-running it will only create missing files.

This prompt adds all files introduced by the five-wave security and resilience
hardening programme (v1.17.0, PRs #27–#31). It covers new source files, ADRs,
compliance docs, governance docs, SRE runbooks, Kubernetes NetworkPolicies,
Alertmanager config, and CI workflows.

---

## 1 — Source: `src/workers/`

Create `src/workers/__init__.py` (empty).

Create `src/workers/request_consumer.py` with the following content exactly:

```python
"""Domain request consumer — reads domain.request.created, drives AgentOrchestrator.

Runs as an asyncio background task in the FastAPI lifespan.

Production note: in a multi-service deployment this worker runs as a separate
process/Deployment, not co-located with the API server. The in-process approach
used here is intentional for self-contained template demonstration.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0003 (Async API Strategy), ADR-0011 (HITL/HOTL Model)
REM:  REM-012 (DLQ + safe offset commit), REM-013 (consumer heartbeat)
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.agents.hitl_gateway import HITLGateway
from src.agents.orchestrator.orchestrator import AgentOrchestrator
from src.agents.request_store import RequestState, RequestStoreProtocol
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.observability.metrics import CONSUMER_HEARTBEAT_TIMESTAMP, DLQ_MESSAGES_COUNTER
from src.shared.config import settings
from src.shared.llm_client import AnthropicLLMClient

if TYPE_CHECKING:
    from src.shared.broker import EventBrokerProtocol

logger = get_logger("request_consumer")

TOPIC = "domain.request.created"


class RequestConsumer:
    """Kafka consumer that drives AgentOrchestrator processing for each submitted request.

    Start via asyncio.create_task(consumer.run()) in the FastAPI lifespan.
    Stop by cancelling the task or calling stop() before cancellation.

    Offset safety (REM-012): enable_auto_commit=False. The offset is committed only
    after _handle() returns — whether the message succeeded or was routed to the DLQ.
    This prevents both silent message loss and infinite reprocessing of poison messages.
    """

    def __init__(
        self,
        store: RequestStoreProtocol,
        audit_logger: AuditLogger,
        hitl_gateway: HITLGateway,
        broker: EventBrokerProtocol,
    ) -> None:
        self._store = store
        self._audit = audit_logger
        self._hitl = hitl_gateway
        self._broker = broker
        self._running = False

    async def run(self) -> None:
        """Main consume loop. Designed to be started as asyncio.create_task()."""
        from aiokafka import AIOKafkaConsumer, TopicPartition  # lazy: keeps tests fast

        self._running = True
        consumer = AIOKafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # REM-012: manual commit after _handle() completes
        )
        await consumer.start()
        logger.info("Request consumer started", topic=TOPIC)
        try:
            async for msg in consumer:
                if not self._running:
                    break
                await self._handle(msg)
                tp = TopicPartition(msg.topic, msg.partition)
                await consumer.commit({tp: msg.offset + 1})
                CONSUMER_HEARTBEAT_TIMESTAMP.labels(settings.kafka_consumer_group).set(
                    datetime.now(UTC).timestamp()
                )
        finally:
            await consumer.stop()
            logger.info("Request consumer stopped")

    async def stop(self) -> None:
        self._running = False

    async def _handle(self, msg: Any) -> None:
        """Process one Kafka message: parse → idempotency check → orchestrate.

        On transient failure: retries up to kafka_consumer_max_retries with exponential
        backoff. On exhaustion: publishes envelope to DLQ topic, increments
        DLQ_MESSAGES_COUNTER, and sets request status to 'failed'. The caller commits
        the offset regardless of outcome.
        """
        try:
            envelope = json.loads(msg.value)
            payload = envelope.get("payload", {})
            request_id = payload.get("request_id")
            trace_id = envelope.get("trace_id")
        except Exception as exc:
            logger.error("Failed to parse event from topic", topic=TOPIC, error=str(exc))
            return

        if not request_id:
            logger.warning("Event missing request_id — skipping", topic=TOPIC)
            return

        existing = await self._store.get(request_id)
        if existing is not None and existing.status != "queued":
            logger.info(
                "Skipping duplicate event",
                request_id=request_id,
                status=existing.status,
            )
            return

        now = datetime.now(UTC)
        created_at = existing.created_at if existing else now

        await self._store.save(
            RequestState(
                request_id=request_id,
                status="processing",
                created_at=created_at,
                updated_at=now,
            )
        )

        last_exc: Exception | None = None
        max_retries = settings.kafka_consumer_max_retries

        for attempt in range(max_retries + 1):
            try:
                llm = AnthropicLLMClient()
                orchestrator = AgentOrchestrator(
                    agent_id=settings.service_name,
                    audit_logger=self._audit,
                    hitl_gateway=self._hitl,
                    llm_client=llm,
                )
                result = await orchestrator.run(
                    raw_input={"request_text": payload.get("request_text", "")},
                    trace_id=trace_id,
                )
                await self._store.save(
                    RequestState(
                        request_id=request_id,
                        status="completed",
                        created_at=created_at,
                        updated_at=datetime.now(UTC),
                        result=result if isinstance(result, dict) else {"output": str(result)},
                    )
                )
                logger.info("Request completed", request_id=request_id)
                return

            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    backoff = (2**attempt) * settings.kafka_consumer_retry_backoff_seconds
                    logger.warning(
                        "Request processing failed — retrying",
                        request_id=request_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        backoff_seconds=backoff,
                        error=str(exc),
                    )
                    await asyncio.sleep(backoff)

        error_msg = str(last_exc) if last_exc else "unknown error"
        logger.error(
            "Request failed after all retries — routing to DLQ",
            request_id=request_id,
            attempts=max_retries + 1,
            error=error_msg,
            dlq_topic=settings.kafka_dlq_topic,
            dlq_routed=True,
        )

        dlq_envelope = {**envelope, "dlq_error": error_msg}
        try:
            await self._broker.publish(
                settings.kafka_dlq_topic,
                dlq_envelope,
                key=request_id,
            )
            DLQ_MESSAGES_COUNTER.labels(
                settings.kafka_consumer_group, settings.kafka_dlq_topic
            ).inc()
        except Exception as dlq_exc:
            logger.error(
                "DLQ publish failed — request status set to failed for manual recovery",
                request_id=request_id,
                error=str(dlq_exc),
            )

        await self._store.save(
            RequestState(
                request_id=request_id,
                status="failed",
                created_at=created_at,
                updated_at=datetime.now(UTC),
                error=error_msg,
            )
        )
```

---

## 2 — Source: `src/api/rest/auth.py` and `src/api/rest/security_headers.py`

Create `src/api/rest/auth.py` with the following content:

```python
"""Operator authentication & authorization for HITL endpoints.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Model)
Threat model: REM-001 (HITL operator impersonation)
"""

from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.shared.config import settings

_bearer = HTTPBearer(auto_error=False)
_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


class Principal(BaseModel):
    sub: str
    role: str | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_UNAUTHENTICATED_HEADERS,
    )


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Missing bearer token")
    try:
        claims: dict[str, Any] = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise _unauthorized("Token missing subject")
    role = claims.get("role")
    return Principal(sub=sub, role=role if isinstance(role, str) else None)


def require_hitl_operator(
    principal: Principal = Depends(get_principal),
) -> Principal:
    if principal.role != settings.hitl_operator_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator role '{settings.hitl_operator_role}' required",
        )
    return principal
```

Create `src/api/rest/security_headers.py` with the following content:

```python
"""HTTP security response headers middleware.

Spec: specs/api/rest-api-design.md (Security Headers)
ADR:  ADR-0002 (Technology Stack Selection)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.shared.config import settings

_CSP_API_ONLY = "default-src 'none'; frame-ancestors 'none'; form-action 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects security headers on every response. HSTS is production-only."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = _CSP_API_ONLY
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
```

---

## 3 — ADRs 0016–0025

Read each of the following files from the repository and recreate them verbatim:

- `docs/adr/ADR-0016-agent-sandbox-execution-policy.md`
- `docs/adr/ADR-0017-agent-memory-architecture.md`
- `docs/adr/ADR-0018-db-encryption-at-rest.md`
- `docs/adr/ADR-0019-redis-tls-value-encryption.md`
- `docs/adr/ADR-0020-finops-cost-allocation.md`
- `docs/adr/ADR-0021-agent-communication-protocol.md`
- `docs/adr/ADR-0022-testing-strategy.md`
- `docs/adr/ADR-0023-frontend-architecture.md`
- `docs/adr/ADR-0024-api-versioning-strategy.md`
- `docs/adr/ADR-0025-language-selection.md`

Also update `docs/adr/README.md` to include index rows for ADR-0016 through ADR-0025.

---

## 4 — Compliance package: `docs/compliance/`

Read each of the following files from the repository and recreate them verbatim:

- `docs/compliance/README.md`
- `docs/compliance/hardening-plan.md`
- `docs/compliance/remediation-register.md`
- `docs/compliance/iso27001-annex-a-control-matrix.md`
- `docs/compliance/soc2-tsc-mapping.md`
- `docs/compliance/slsa-supply-chain-assessment.md`
- `docs/compliance/trust-summary.md`
- `docs/compliance/security-questionnaire-quickref.md`

---

## 5 — Governance: `docs/governance/`

Read `docs/governance/owner-onboarding.md` from the repository and recreate it verbatim.

---

## 6 — SRE runbooks (new)

Read each of the following files from the repository and recreate them verbatim:

- `docs/sre/runbooks/dlq-accumulating.md`
- `docs/sre/runbooks/redis-ha.md`
- `docs/sre/runbooks/db-key-rotation.md`

---

## 7 — Kubernetes NetworkPolicies

Read each of the following files from the repository and recreate them verbatim:

- `infrastructure/k8s/network-policies/README.md`
- `infrastructure/k8s/network-policies/default-deny-ingress.yaml`
- `infrastructure/k8s/network-policies/api-gateway.yaml`
- `infrastructure/k8s/network-policies/monitoring.yaml`
- `infrastructure/k8s/network-policies/istio-peer-auth.yaml`

---

## 8 — Alertmanager

Read `infrastructure/monitoring/alertmanager/alertmanager.yml` from the repository and recreate it verbatim.

---

## 9 — CI workflows (new)

Read each of the following files from the repository and recreate them verbatim:

- `.github/workflows/codeql.yml`
- `.github/workflows/pr-governance.yml`

Also read `.trivyignore` from the repository root and recreate it verbatim.

---

## 10 — Validation

After creating all files above, confirm:

- [ ] `src/workers/__init__.py` exists (empty)
- [ ] `src/workers/request_consumer.py` exports `RequestConsumer` with `run()`, `stop()`, `_handle()`
- [ ] `RequestConsumer.__init__` accepts `broker: EventBrokerProtocol` (REM-012)
- [ ] `src/api/rest/auth.py` exports `Principal`, `get_principal`, `require_hitl_operator`
- [ ] `src/api/rest/security_headers.py` exports `SecurityHeadersMiddleware`
- [ ] All 10 new ADR files (0016–0025) exist in `docs/adr/`
- [ ] All 8 compliance docs exist in `docs/compliance/`
- [ ] `docs/governance/owner-onboarding.md` exists
- [ ] All 3 new SRE runbooks exist in `docs/sre/runbooks/`
- [ ] All 5 NetworkPolicy files exist in `infrastructure/k8s/network-policies/`
- [ ] `infrastructure/monitoring/alertmanager/alertmanager.yml` exists
- [ ] `.github/workflows/codeql.yml` and `pr-governance.yml` exist
- [ ] `.trivyignore` exists at repo root
- [ ] No real credentials, secrets, or PII in any file
