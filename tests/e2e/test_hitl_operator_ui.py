"""E2E — HITL operator decision flow.

CUJ:   CUJ-002 (HITL Decision Flow)
Spec:  specs/ai/hitl-hotl.md, specs/security/rbac-model.md
ADR:   ADR-0011 (HITL/HOTL Model)
SLO:   p95 decision latency ≤ 300 s; HITL gateway availability ≥ 99.9%

Tests the complete operator journey:
  1. A user submits a request that triggers HITL escalation.
  2. The HITL operator sees the request in the pending queue.
  3. The operator submits an APPROVE decision.
  4. The request status reflects the decision.
  5. An REJECT decision is also tested.
  6. Attempting to decide an unknown / expired request returns 404.

Transport:
  Default   — ASGI in-process (no real server required; uses InMemory stores)
  Live mode — set BASE_URL=http://localhost:8000 to run against a real server

Test markers: e2e
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.e2e

# ── Transport selection ───────────────────────────────────────────────────────

BASE_URL = os.environ.get("BASE_URL", "")
_LIVE = bool(BASE_URL)


def _build_asgi_app() -> FastAPI:
    """Minimal FastAPI app wiring the HITL and requests routers with in-memory stores."""
    from src.agents.hitl_gateway import HITLGateway
    from src.agents.hitl_store import InMemoryHITLStore
    from src.agents.request_store import InMemoryRequestStore
    from src.agents.tool_executor import ToolExecutor
    from src.api.rest.routers.hitl import router as hitl_router
    from src.api.rest.routers.requests import router as req_router
    from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
    from src.shared.broker import InMemoryBroker
    from src.workers.approval_consumer import ApprovalConsumer

    audit = AuditLogger(InMemoryAuditStorage())
    store = InMemoryHITLStore()
    broker = InMemoryBroker()
    # The gateway publishes decisions to the broker; the ApprovalConsumer (ADR-0086) is
    # subscribed so an APPROVED decision executes the stored action in-process (CUJ-002 step 4).
    gateway = HITLGateway(audit_logger=audit, broker=broker, store=store)
    request_store = InMemoryRequestStore()

    app = FastAPI()
    app.include_router(req_router, prefix="/v1")
    app.include_router(hitl_router, prefix="/v1/hitl")
    app.state.request_store = request_store
    app.state.broker = broker
    app.state.hitl_gateway = gateway
    app.state.audit_logger = audit
    app.state.approval_consumer = ApprovalConsumer(
        hitl_gateway=gateway,
        request_store=request_store,
        tool_executor=ToolExecutor(audit),
        audit_logger=audit,
        broker=broker,
    )
    from src.workers.approval_consumer import TOPICS

    for topic in TOPICS:
        broker.subscribe(topic, app.state.approval_consumer.handle_event)
    return app


async def _make_client() -> tuple[AsyncClient, Any]:
    """Return (client, context_manager) suited to the chosen transport."""
    if _LIVE:
        client = AsyncClient(base_url=BASE_URL, timeout=10.0, headers=_operator_headers())
        return client, client
    app = _build_asgi_app()
    client = AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=_operator_headers()
    )
    return client, client


# ── Helpers ───────────────────────────────────────────────────────────────────

_SYNTHETIC_APPROVER = "operator-00000000-0000-0000-0000-000000000001"


def _operator_headers() -> dict[str, str]:
    """Bearer token for the HITL operator (REM-001: approver identity comes from the JWT).

    Live mode honours ``HITL_OPERATOR_TOKEN``; otherwise a token is minted with the same
    ``SECRET_KEY`` the server under test uses.
    """
    token = os.environ.get("HITL_OPERATOR_TOKEN")
    if not token:
        import jwt

        from src.shared.config import settings

        token = jwt.encode(
            {
                "sub": _SYNTHETIC_APPROVER,
                "role": settings.hitl_operator_role,
                "exp": datetime.now(UTC) + timedelta(hours=1),
            },
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
    return {"Authorization": f"Bearer {token}"}


_SYNTHETIC_RATIONALE = "Action verified against approved scope. Risk within accepted bounds."


async def _seed_hitl_request(gateway: Any) -> str:
    """Directly seed a pending HITL request (ASGI mode only)."""
    from src.agents.hitl_gateway import HITLRequest

    req = HITLRequest(
        request_id=str(uuid.uuid4()),
        agent_id="test-agent-00000000",
        action_type="write_file",
        action_parameters={"path": "/tmp/report.txt"},
        risk_score=0.85,
        context_summary="Agent proposes writing a report file.",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await gateway._store.save(req)
    return req.request_id


# ── Tests — HITL status endpoint ──────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLStatusEndpoint:
    async def test_hitl_status_returns_operational(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_asgi_app()), base_url="http://test"
        ) as client:
            response = await client.get("/v1/hitl/status")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "operational"
        assert isinstance(body["pending_count"], int)
        assert body["pending_count"] >= 0

    async def test_hitl_status_reflects_queue_depth(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        rid = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.get("/v1/hitl/status")

        assert response.status_code == 200
        assert response.json()["pending_count"] >= 1
        _ = rid  # seeded for queue depth assertion


# ── Tests — APPROVE decision ──────────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLApproveDecision:
    async def test_approve_returns_200_with_approved_decision(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": _SYNTHETIC_RATIONALE,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "APPROVED"
        assert body["request_id"] == request_id

    async def test_approve_removes_request_from_pending_queue(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            depth_before = (await client.get("/v1/hitl/status")).json()["pending_count"]
            await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": _SYNTHETIC_RATIONALE,
                },
            )
            depth_after = (await client.get("/v1/hitl/status")).json()["pending_count"]

        assert depth_after < depth_before

    async def test_approve_decision_field_matches_contracted_enum(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            body = (
                await client.post(
                    f"/v1/hitl/requests/{request_id}/decision",
                    json={
                        "decision": "APPROVED",
                        "rationale": _SYNTHETIC_RATIONALE,
                    },
                )
            ).json()

        assert body["decision"] in {"APPROVED", "REJECTED"}


# ── Tests — REJECT decision ───────────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLRejectDecision:
    async def test_reject_returns_200_with_rejected_decision(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "REJECTED",
                    "rationale": "Action exceeds approved risk threshold for this action_type.",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["decision"] == "REJECTED"
        assert body["request_id"] == request_id

    async def test_short_rationale_returns_422(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "REJECTED",
                    "rationale": "too short",  # < 10 chars
                },
            )

        assert response.status_code == 422


# ── Tests — not found / expired ───────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLNotFound:
    async def test_unknown_request_id_returns_404(self) -> None:
        app = _build_asgi_app()
        unknown_id = "00000000-0000-0000-0000-000000000099"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{unknown_id}/decision",
                json={
                    "decision": "APPROVED",
                    "rationale": _SYNTHETIC_RATIONALE,
                },
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_double_decision_on_same_request_returns_404(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            decision_payload = {
                "decision": "APPROVED",
                "rationale": _SYNTHETIC_RATIONALE,
            }
            first = await client.post(
                f"/v1/hitl/requests/{request_id}/decision", json=decision_payload
            )
            second = await client.post(
                f"/v1/hitl/requests/{request_id}/decision", json=decision_payload
            )

        assert first.status_code == 200
        # Request is no longer pending after first decision — second should 404
        assert second.status_code == 404


# ── Tests — invalid decision value ────────────────────────────────────────────


@pytest.mark.e2e
class TestHITLValidation:
    async def test_invalid_decision_enum_returns_422(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={
                    "decision": "MAYBE",  # not in enum
                    "rationale": _SYNTHETIC_RATIONALE,
                },
            )

        assert response.status_code == 422

    async def test_missing_rationale_returns_422(self) -> None:
        app = _build_asgi_app()
        gateway = app.state.hitl_gateway
        request_id = await _seed_hitl_request(gateway)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{request_id}/decision",
                json={"decision": "APPROVED"},  # rationale missing; approver comes from the JWT
            )

        assert response.status_code == 422


# ── Tests — approval executes the stored action (ADR-0086) ───────────────────


async def _seed_suspended_domain_request(app: FastAPI, hitl_id: str, action_type: str) -> str:
    """Seed a registered-tool HITL request plus the domain request waiting on it."""
    from src.agents.hitl_gateway import HITLRequest
    from src.agents.request_store import RequestState

    now = datetime.now(UTC)
    await app.state.hitl_gateway._store.save(
        HITLRequest(
            request_id=hitl_id,
            agent_id="test-agent-00000000",
            action_type=action_type,
            action_parameters={"format": "csv", "dataset": "synthetic-orders"},
            risk_score=0.5,
            context_summary="Agent proposes generating a synthetic report.",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
    )
    domain_id = str(uuid.uuid4())
    await app.state.request_store.save(
        RequestState(
            request_id=domain_id,
            status="waiting_for_human_approval",
            created_at=now,
            updated_at=now,
            result={"status": "waiting_for_human_approval", "hitl_request_id": hitl_id},
        )
    )
    return domain_id


@pytest.mark.e2e
class TestHITLApprovalExecutesAction:
    """CUJ-002 step 4 (W12-T2): approval is not just recorded — the action runs and the
    domain request leaves `waiting_for_human_approval` with an honest terminal status."""

    async def test_approved_registered_tool_executes_and_completes_request(self) -> None:
        if _LIVE:
            pytest.skip("in-process wiring assertion; live mode covers the API surface only")
        app = _build_asgi_app()
        hitl_id = str(uuid.uuid4())
        domain_id = await _seed_suspended_domain_request(app, hitl_id, "generate-report")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            response = await client.post(
                f"/v1/hitl/requests/{hitl_id}/decision",
                json={"decision": "APPROVED", "rationale": _SYNTHETIC_RATIONALE},
            )
            assert response.status_code == 200
            status = await client.get(f"/v1/requests/{domain_id}")

        assert status.status_code == 200
        body = status.json()
        assert body["status"] == "completed", body
        assert body["result"]["outcome"] == "EXECUTED"
        assert body["result"]["hitl_request_id"] == hitl_id

    async def test_rejected_decision_settles_request_as_rejected_without_executing(self) -> None:
        if _LIVE:
            pytest.skip("in-process wiring assertion; live mode covers the API surface only")
        app = _build_asgi_app()
        hitl_id = str(uuid.uuid4())
        domain_id = await _seed_suspended_domain_request(app, hitl_id, "generate-report")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            await client.post(
                f"/v1/hitl/requests/{hitl_id}/decision",
                json={"decision": "REJECTED", "rationale": _SYNTHETIC_RATIONALE},
            )
            body = (await client.get(f"/v1/requests/{domain_id}")).json()

        assert body["status"] == "rejected", body
        assert body["result"].get("outcome") == "REJECTED"

    async def test_approved_unregistered_tool_fails_honestly(self) -> None:
        """Approval never bypasses the tool registry (ADR-0039): the request ends `failed`."""
        if _LIVE:
            pytest.skip("in-process wiring assertion; live mode covers the API surface only")
        app = _build_asgi_app()
        hitl_id = str(uuid.uuid4())
        domain_id = await _seed_suspended_domain_request(app, hitl_id, "write_file")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=_operator_headers(),
        ) as client:
            await client.post(
                f"/v1/hitl/requests/{hitl_id}/decision",
                json={"decision": "APPROVED", "rationale": _SYNTHETIC_RATIONALE},
            )
            body = (await client.get(f"/v1/requests/{domain_id}")).json()

        assert body["status"] == "failed", body
        assert "not registered" in (body.get("error") or "")
