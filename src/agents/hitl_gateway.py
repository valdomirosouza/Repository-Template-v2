"""HITL Gateway — mandatory human approval flow for consequential agent actions.

All agent actions with real-world effects must route through this module.
Timeout never auto-approves — it always rejects.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from opentelemetry import trace
from opentelemetry.trace import Link, SpanContext, TraceFlags

from src.agents.feedback_learner import FeedbackLearner, default_feedback_learner
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.observability.metrics import (
    ACTIVE_HITL_REQUESTS,
    record_hitl_decision,
)
from src.observability.span_hierarchy import SPAN_TOOL_HITL_GATEWAY, tracer
from src.shared.config import settings
from src.shared.models import AuditEvent

logger = get_logger("hitl_gateway")


class HITLStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class HITLRequest:
    request_id: str
    agent_id: str
    action_type: str
    action_parameters: dict[str, Any]
    risk_score: float
    context_summary: str  # PII-masked summary for the human reviewer
    created_at: datetime
    expires_at: datetime
    status: HITLStatus = HITLStatus.PENDING
    # OTel trace context captured at submission time for linked hitl.decision span (OTEL-001 §7)
    otel_trace_id: str = ""
    otel_span_id: str = ""


@dataclass
class HITLDecision:
    request_id: str
    decision: HITLStatus  # APPROVED or REJECTED only
    approver_id: str
    rationale: str
    decided_at: datetime


class HITLGatewayError(Exception):
    """Raised for invalid state transitions or missing requests."""


class HITLStore(Protocol):
    """Persistence contract for HITL requests.

    Implementations: InMemoryHITLStore (local/test) and HITLRedisStore (production).
    See src/agents/hitl_store.py.
    """

    async def save(self, request: HITLRequest) -> None: ...

    async def get(self, request_id: str) -> HITLRequest | None: ...

    async def get_active(self, request_id: str) -> HITLRequest | None: ...

    async def pending_count(self) -> int: ...

    async def list_pending(self) -> list[HITLRequest]: ...

    async def get_pending_expired(self, now: datetime) -> list[HITLRequest]: ...

    async def evict(self, request_id: str) -> None: ...

    async def archive(self, request_id: str, request: HITLRequest) -> None: ...


class HITLGateway:
    """Manages the lifecycle of HITL approval requests.

    Delegates persistence to a HITLStore. Defaults to InMemoryHITLStore when no
    store is provided; production deployments should supply HITLRedisStore.
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        broker: Any | None = None,
        timeout_seconds: int | None = None,
        store: HITLStore | None = None,
        feedback_learner: FeedbackLearner | None = None,
    ) -> None:
        self._audit = audit_logger
        self._broker = broker
        default_timeout = settings.hitl_approval_timeout_seconds
        self._timeout = timeout_seconds if timeout_seconds is not None else default_timeout
        if store is None:
            from src.agents.hitl_store import InMemoryHITLStore  # lazy: avoids circular import

            store = InMemoryHITLStore()
        self._store: HITLStore = store
        self._lock = asyncio.Lock()
        self._learner = feedback_learner or default_feedback_learner

    async def submit_for_approval(self, request: HITLRequest) -> HITLRequest:
        """Persist the request and publish agent.action.proposed to the broker.

        Raises HITLGatewayError if the store has reached hitl_max_pending_requests.
        """
        now = datetime.now(UTC)
        request.created_at = now
        request.expires_at = now + timedelta(seconds=self._timeout)
        request.status = HITLStatus.PENDING

        # Capture the current OTel span context so record_decision() can create a linked span.
        current_ctx = trace.get_current_span().get_span_context()
        if current_ctx.is_valid:
            request.otel_trace_id = format(current_ctx.trace_id, "032x")
            request.otel_span_id = format(current_ctx.span_id, "016x")

        async with self._lock:
            count = await self._store.pending_count()
            if count >= settings.hitl_max_pending_requests:
                raise HITLGatewayError(
                    f"HITL request store at capacity ({settings.hitl_max_pending_requests}). "
                    "Expire stale requests or increase hitl_max_pending_requests."
                )
            await self._store.save(request)
        ACTIVE_HITL_REQUESTS.labels(request.agent_id).inc()

        # Write audit record before notifying broker
        await self._audit.log_event(
            AuditEvent(
                event_type="hitl.request.submitted",
                agent_id=request.agent_id,
                action=request.action_type,
                outcome="PENDING",
                risk_score=request.risk_score,
                metadata={"request_id": request.request_id},
                trace_id=None,
            )
        )

        if self._broker is not None:
            await self._broker.publish(
                "agent.action.proposed",
                {
                    "request_id": request.request_id,
                    "agent_id": request.agent_id,
                    "action_type": request.action_type,
                    "risk_score": request.risk_score,
                    "context_summary": request.context_summary,
                    "expires_at": request.expires_at.isoformat(),
                },
            )

        logger.info(
            "HITL request submitted",
            request_id=request.request_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            risk_score=request.risk_score,
        )

        return request

    async def record_decision(self, decision: HITLDecision) -> HITLRequest:
        """Record a human approval or rejection and publish the outcome event."""

        # Phase 1: state transition under lock.
        expired = False
        async with self._lock:
            request = await self._store.get_active(decision.request_id)
            if request is None:
                raise HITLGatewayError(f"Request {decision.request_id} not found")

            if request.status != HITLStatus.PENDING:
                raise HITLGatewayError(
                    f"Request {decision.request_id} is not PENDING (current: {request.status})"
                )

            if decision.decision not in (HITLStatus.APPROVED, HITLStatus.REJECTED):
                raise HITLGatewayError(
                    f"Decision must be APPROVED or REJECTED, got: {decision.decision}"
                )

            if self._is_expired(request):
                request.status = HITLStatus.EXPIRED
                expired = True
            else:
                request.status = decision.decision
                await self._store.save(request)

        # Phase 2: I/O outside the lock.
        if expired:
            async with self._lock:
                await self._store.archive(decision.request_id, request)
            await self._expire_audit(request)
            raise HITLGatewayError(
                f"Request {decision.request_id} expired before decision was recorded"
            )

        ACTIVE_HITL_REQUESTS.labels(request.agent_id).dec()

        async with self._lock:
            await self._store.archive(decision.request_id, request)

        wait_seconds = (decision.decided_at - request.created_at).total_seconds()

        await self._audit.log_event(
            AuditEvent(
                event_type="hitl.decision.recorded",
                agent_id=request.agent_id,
                action=request.action_type,
                outcome=decision.decision.value,
                approver_id=decision.approver_id,
                metadata={
                    "request_id": request.request_id,
                    "rationale": decision.rationale,
                    "wait_seconds": wait_seconds,
                },
            )
        )

        record_hitl_decision(
            agent_id=request.agent_id,
            action_type=request.action_type,
            approved=(decision.decision == HITLStatus.APPROVED),
            wait_seconds=wait_seconds,
        )

        # Emit a linked hitl.decision span referencing the original agent.task trace (OTEL-001 §7).
        self._emit_decision_span(request, decision, wait_seconds)

        topic = (
            "agent.action.approved"
            if decision.decision == HITLStatus.APPROVED
            else "agent.action.rejected"
        )
        if self._broker is not None:
            await self._broker.publish(
                topic,
                {
                    "request_id": request.request_id,
                    "decision": decision.decision.value,
                    "rationale": decision.rationale,
                },
            )

        logger.info(
            "HITL decision recorded",
            request_id=request.request_id,
            decision=decision.decision.value,
        )

        # Learn stage: record HITL decision outcome for future precedent retrieval.
        self._learner.record(
            FeedbackLearner.feedback_from_hitl_decision(
                action_type=request.action_type,
                action_parameters=request.action_parameters,
                decision=decision.decision.value.lower(),
                rationale=decision.rationale or "",
                agent_id=request.agent_id,
                request_id=request.request_id,
            )
        )

        return request

    def _emit_decision_span(
        self,
        request: HITLRequest,
        decision: HITLDecision,
        wait_seconds: float,
    ) -> None:
        """Create a hitl.decision span linked to the original agent.task trace context."""
        links: list[Link] = []
        if request.otel_trace_id and request.otel_span_id:
            try:
                link_ctx = SpanContext(
                    trace_id=int(request.otel_trace_id, 16),
                    span_id=int(request.otel_span_id, 16),
                    is_remote=True,
                    trace_flags=TraceFlags(TraceFlags.SAMPLED),
                )
                links.append(Link(context=link_ctx))
            except (ValueError, OverflowError):
                pass  # malformed context — emit span without link

        with tracer.start_as_current_span(SPAN_TOOL_HITL_GATEWAY, links=links) as span:
            span.set_attributes(
                {
                    "hitl.decision": decision.decision.value.lower(),
                    "hitl.decided_by": decision.approver_id,
                    "hitl.wait_duration_seconds": wait_seconds,
                    "hitl.action_type": request.action_type,
                    "hitl.risk_score": request.risk_score,
                }
            )

    async def get_request(self, request_id: str) -> HITLRequest | None:
        async with self._lock:
            return await self._store.get(request_id)

    async def list_pending(self) -> list[HITLRequest]:
        """Return all currently PENDING requests for the reviewer queue (read-only).

        Does not mutate state or alter approval logic — purely a read for the operator UI.
        """
        async with self._lock:
            return await self._store.list_pending()

    async def expire_stale_requests(self) -> list[str]:
        """Mark all PENDING requests past their expires_at as EXPIRED and archive them.

        Never auto-approves — timeout always results in EXPIRED (treated as rejection).
        Archiving expired entries keeps them accessible for audit while freeing capacity.
        """
        now = datetime.now(UTC)
        async with self._lock:
            candidates = await self._store.get_pending_expired(now)
        expired_ids: list[str] = []
        for req in candidates:
            await self._expire_single(req)
            async with self._lock:
                await self._store.archive(req.request_id, req)
            expired_ids.append(req.request_id)
        return expired_ids

    async def _expire_single(self, request: HITLRequest) -> None:
        """Set status to EXPIRED then emit audit + broker events."""
        request.status = HITLStatus.EXPIRED
        await self._expire_audit(request)

    async def _expire_audit(self, request: HITLRequest) -> None:
        """Emit audit log and broker event for an already-expired request."""
        ACTIVE_HITL_REQUESTS.labels(request.agent_id).dec()

        await self._audit.log_event(
            AuditEvent(
                event_type="hitl.request.expired",
                agent_id=request.agent_id,
                action=request.action_type,
                outcome="EXPIRED_AUTO_REJECTED",
                metadata={"request_id": request.request_id},
            )
        )

        if self._broker is not None:
            await self._broker.publish(
                "agent.action.expired",
                {"request_id": request.request_id, "outcome": "EXPIRED_AUTO_REJECTED"},
            )

        logger.warning(
            "HITL request expired — auto-rejected",
            request_id=request.request_id,
            agent_id=request.agent_id,
        )

    def _is_expired(self, request: HITLRequest) -> bool:
        return datetime.now(UTC) >= request.expires_at
