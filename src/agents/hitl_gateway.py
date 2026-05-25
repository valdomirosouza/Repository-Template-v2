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
from typing import Any

from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.observability.metrics import (
    ACTIVE_HITL_REQUESTS,
    record_hitl_decision,
)
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


@dataclass
class HITLDecision:
    request_id: str
    decision: HITLStatus  # APPROVED or REJECTED only
    approver_id: str
    rationale: str
    decided_at: datetime


class HITLGatewayError(Exception):
    """Raised for invalid state transitions or missing requests."""


class HITLGateway:
    """Manages the lifecycle of HITL approval requests.

    Maintains an in-memory request store for the running process; a production
    deployment should replace _requests with a persistent store (Redis or DB).
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        broker: Any | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._audit = audit_logger
        self._broker = broker
        default_timeout = settings.hitl_approval_timeout_seconds
        self._timeout = timeout_seconds if timeout_seconds is not None else default_timeout
        self._requests: dict[str, HITLRequest] = {}
        self._expired: dict[str, HITLRequest] = {}  # retains expired entries for audit/lookup
        self._lock = asyncio.Lock()

    async def submit_for_approval(self, request: HITLRequest) -> HITLRequest:
        """Persist the request and publish agent.action.proposed to the broker.

        Raises HITLGatewayError if the store has reached hitl_max_pending_requests.
        """
        now = datetime.now(UTC)
        request.created_at = now
        request.expires_at = now + timedelta(seconds=self._timeout)
        request.status = HITLStatus.PENDING

        async with self._lock:
            if len(self._requests) >= settings.hitl_max_pending_requests:
                raise HITLGatewayError(
                    f"HITL request store at capacity ({settings.hitl_max_pending_requests}). "
                    "Expire stale requests or increase hitl_max_pending_requests."
                )
            self._requests[request.request_id] = request
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

        # Phase 1: atomic state transition — lock held only for in-memory mutation.
        # I/O (audit, broker) happens outside the lock to minimise contention.
        expired = False
        async with self._lock:
            request = self._requests.get(decision.request_id)
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

        # Phase 2: I/O outside lock.
        if expired:
            async with self._lock:
                self._requests.pop(decision.request_id, None)
                self._expired[decision.request_id] = request
            await self._expire_audit(request)
            raise HITLGatewayError(
                f"Request {decision.request_id} expired before decision was recorded"
            )

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

        return request

    async def get_request(self, request_id: str) -> HITLRequest | None:
        async with self._lock:
            return self._requests.get(request_id) or self._expired.get(request_id)

    async def expire_stale_requests(self) -> list[str]:
        """Mark all PENDING requests past their expires_at as EXPIRED and evict them.

        Never auto-approves — timeout always results in EXPIRED (treated as rejection).
        Evicting expired entries prevents unbounded growth of the in-memory store.
        """
        expired_ids: list[str] = []
        async with self._lock:
            candidates = [
                req
                for req in self._requests.values()
                if req.status == HITLStatus.PENDING and self._is_expired(req)
            ]
        for req in candidates:
            await self._expire_single(req)
            async with self._lock:
                self._requests.pop(req.request_id, None)
                self._expired[req.request_id] = req
            expired_ids.append(req.request_id)
        return expired_ids

    async def _expire_single(self, request: HITLRequest) -> None:
        """Set status to EXPIRED (state) then emit audit + broker events (I/O)."""
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
