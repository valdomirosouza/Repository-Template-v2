"""Override service — the HOTL override window and compensation flow.

When an action executes under HOTL it is *registered* here with an override window
(default 5 minutes, ``settings.hotl_override_window_seconds``). A reviewer may
request an override within the window; the service then attempts the action's
compensating action to undo the effect.

Event chain (emitted as immutable audit records):

    agent.action.override.requested
      → agent.action.compensation.started
        → agent.action.compensation.succeeded   (compensation ran)
        | agent.action.compensation.failed       (compensation raised → escalation)
    agent.action.confirmed                        (window elapsed, no override)
    agent.action.escalation.raised                (failed/absent compensation)

Policy:
  - Override outside the window is rejected (OverrideWindowExpiredError), audited.
  - Every override records actor, timestamp, and reason (audit metadata).
  - A failed or impossible compensation raises an escalation event for humans.

Spec: specs/ai/hitl-hotl.md (Override Procedure)
ADR:  ADR-0055 (HOTL operationalization), ADR-0011
"""

from __future__ import annotations

import datetime
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.agents.compensation_registry import CompensationRegistry
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.shared.config import settings
from src.shared.models import AuditEvent

logger = get_logger("override_service")

# ── Event type constants ──────────────────────────────────────────────────────
EVENT_OVERRIDE_REQUESTED = "agent.action.override.requested"
EVENT_COMPENSATION_STARTED = "agent.action.compensation.started"
EVENT_COMPENSATION_SUCCEEDED = "agent.action.compensation.succeeded"
EVENT_COMPENSATION_FAILED = "agent.action.compensation.failed"
EVENT_ESCALATION_RAISED = "agent.action.escalation.raised"
EVENT_ACTION_CONFIRMED = "agent.action.confirmed"

# Async callable that runs a compensating action: (action_type, parameters) -> result.
Compensator = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class UnknownHOTLActionError(KeyError):
    """Raised when an override targets an action that was never registered."""


class OverrideWindowExpiredError(Exception):
    """Raised when an override is requested after the window has closed."""


@dataclass
class HOTLRecord:
    """In-memory record of an executed HOTL action and its override window."""

    action_id: str
    agent_id: str
    action_type: str
    parameters: dict[str, Any]
    risk_score: float
    executed_at: datetime.datetime
    expires_at: datetime.datetime
    # ACTIVE | CONFIRMED | COMPENSATED | COMPENSATION_FAILED
    # | OVERRIDDEN_NO_COMPENSATION | WINDOW_EXPIRED
    status: str = "ACTIVE"
    trace_id: str | None = None


@dataclass
class OverrideResult:
    """Outcome of an override request."""

    action_id: str
    outcome: str  # COMPENSATED | COMPENSATION_FAILED | NO_COMPENSATION
    compensating_action: str | None
    escalated: bool
    detail: str = ""


class OverrideService:
    """Manages HOTL override windows and compensation execution."""

    def __init__(
        self,
        audit_logger: AuditLogger,
        compensation_registry: CompensationRegistry | None = None,
        override_window_seconds: int | None = None,
        compensator: Compensator | None = None,
    ) -> None:
        self._audit = audit_logger
        self._comp = compensation_registry or CompensationRegistry()
        self._window = (
            override_window_seconds
            if override_window_seconds is not None
            else settings.hotl_override_window_seconds
        )
        self._compensator = compensator
        self._records: dict[str, HOTLRecord] = {}

    # ── Registration ────────────────────────────────────────────────────────

    def register_executed_action(
        self,
        *,
        action_id: str,
        agent_id: str,
        action_type: str,
        parameters: dict[str, Any],
        risk_score: float,
        executed_at: datetime.datetime | None = None,
        trace_id: str | None = None,
    ) -> HOTLRecord:
        """Record a just-executed HOTL action and open its override window."""
        now = executed_at or _utcnow()
        record = HOTLRecord(
            action_id=action_id,
            agent_id=agent_id,
            action_type=action_type,
            parameters=parameters,
            risk_score=risk_score,
            executed_at=now,
            expires_at=now + datetime.timedelta(seconds=self._window),
            trace_id=trace_id,
        )
        self._records[action_id] = record
        return record

    def get(self, action_id: str) -> HOTLRecord:
        if action_id not in self._records:
            raise UnknownHOTLActionError(f"no HOTL record for action_id '{action_id}'")
        return self._records[action_id]

    def is_within_window(self, action_id: str, now: datetime.datetime | None = None) -> bool:
        record = self.get(action_id)
        return (now or _utcnow()) <= record.expires_at

    # ── Override flow ─────────────────────────────────────────────────────────

    async def request_override(
        self,
        *,
        action_id: str,
        actor: str,
        reason: str,
        now: datetime.datetime | None = None,
    ) -> OverrideResult:
        """Request an override; attempt compensation if within the window.

        Raises OverrideWindowExpiredError if the window has closed.
        """
        record = self.get(action_id)
        now = now or _utcnow()

        await self._emit(
            EVENT_OVERRIDE_REQUESTED,
            record,
            outcome="OVERRIDE_REQUESTED",
            metadata={"actor": actor, "reason": reason, "requested_at": now.isoformat()},
        )

        if now > record.expires_at:
            record.status = "WINDOW_EXPIRED"
            logger.warning("override_service.window_expired", action_id=action_id, actor=actor)
            raise OverrideWindowExpiredError(
                f"override window for action '{action_id}' closed at "
                f"{record.expires_at.isoformat()}"
            )

        compensating = self._comp.get_compensating_action(record.action_type)
        await self._emit(
            EVENT_COMPENSATION_STARTED,
            record,
            outcome="COMPENSATION_STARTED",
            metadata={"actor": actor, "compensating_action": compensating},
        )

        # No compensating action declared (or non-reversible) → manual remediation.
        if compensating is None or self._compensator is None:
            record.status = "OVERRIDDEN_NO_COMPENSATION"
            detail = (
                "no compensating action declared"
                if compensating is None
                else "no compensator configured"
            )
            await self._escalate(
                record,
                actor=actor,
                reason=f"override requested but {detail}; manual remediation required",
            )
            return OverrideResult(
                action_id=action_id,
                outcome="NO_COMPENSATION",
                compensating_action=compensating,
                escalated=True,
                detail=detail,
            )

        # Attempt compensation.
        try:
            await self._compensator(compensating, record.parameters)
        except Exception as exc:  # compensation failed → escalate
            record.status = "COMPENSATION_FAILED"
            await self._emit(
                EVENT_COMPENSATION_FAILED,
                record,
                outcome="COMPENSATION_FAILED",
                metadata={"actor": actor, "compensating_action": compensating, "error": str(exc)},
            )
            await self._escalate(
                record,
                actor=actor,
                reason=f"compensation '{compensating}' failed: {exc}",
            )
            return OverrideResult(
                action_id=action_id,
                outcome="COMPENSATION_FAILED",
                compensating_action=compensating,
                escalated=True,
                detail=str(exc),
            )

        record.status = "COMPENSATED"
        await self._emit(
            EVENT_COMPENSATION_SUCCEEDED,
            record,
            outcome="COMPENSATION_SUCCEEDED",
            metadata={"actor": actor, "compensating_action": compensating},
        )
        return OverrideResult(
            action_id=action_id,
            outcome="COMPENSATED",
            compensating_action=compensating,
            escalated=False,
        )

    async def confirm(self, action_id: str, now: datetime.datetime | None = None) -> HOTLRecord:
        """Confirm an action after its window elapsed with no override."""
        record = self.get(action_id)
        if (now or _utcnow()) <= record.expires_at:
            logger.info("override_service.confirm_before_window_close", action_id=action_id)
        record.status = "CONFIRMED"
        await self._emit(
            EVENT_ACTION_CONFIRMED,
            record,
            outcome="CONFIRMED",
            metadata={"confirmed_at": (now or _utcnow()).isoformat()},
        )
        return record

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _emit(
        self,
        event_type: str,
        record: HOTLRecord,
        *,
        outcome: str,
        metadata: dict[str, Any],
    ) -> None:
        await self._audit.log_event(
            AuditEvent(
                event_type=event_type,
                agent_id=record.agent_id,
                action=record.action_type,
                outcome=outcome,
                risk_score=record.risk_score,
                metadata={"action_id": record.action_id, **metadata},
                trace_id=record.trace_id,
            )
        )

    async def _escalate(self, record: HOTLRecord, *, actor: str, reason: str) -> None:
        logger.warning(
            "override_service.escalation",
            action_id=record.action_id,
            action_type=record.action_type,
            reason=reason,
        )
        await self._emit(
            EVENT_ESCALATION_RAISED,
            record,
            outcome="ESCALATED",
            metadata={"actor": actor, "reason": reason},
        )
