"""HOTL monitor — drives the post-execution lifecycle of HOTL actions.

When an action executes under HOTL (Human On The Loop), the reviewer must be
notified within an SLO (default 60s) and given an override window. This monitor:

  1. Emits ``agent.action.hotl.notification.sent`` (records latency vs. the SLO).
  2. Registers the executed action with the OverrideService, opening its window.
  3. Exposes drift detection — actions whose notification missed the SLO.

The orchestrator calls :meth:`on_hotl_executed` after a HOTL action returns
EXECUTED. It is optional: when no monitor is injected, behaviour is unchanged.

Spec: specs/ai/hitl-hotl.md (HOTL Specification — notify within 60s, 5-min override)
ADR:  ADR-0055 (HOTL operationalization), ADR-0011
"""

from __future__ import annotations

import datetime
from collections.abc import Awaitable, Callable
from typing import Any

from src.agents.override_service import HOTLRecord, OverrideService
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.shared.config import settings
from src.shared.models import AuditEvent

logger = get_logger("hotl_monitor")

EVENT_NOTIFICATION_SENT = "agent.action.hotl.notification.sent"

# Async callable that delivers the reviewer notification: (record) -> None.
Notifier = Callable[[HOTLRecord], Awaitable[None]]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class HOTLMonitor:
    """Notifies reviewers of HOTL actions and opens their override window."""

    def __init__(
        self,
        audit_logger: AuditLogger,
        override_service: OverrideService,
        notification_slo_seconds: int | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self._audit = audit_logger
        self._override = override_service
        self._slo = (
            notification_slo_seconds
            if notification_slo_seconds is not None
            else settings.hotl_notification_slo_seconds
        )
        self._notifier = notifier

    async def on_hotl_executed(
        self,
        *,
        action_id: str,
        agent_id: str,
        action_type: str,
        parameters: dict[str, Any],
        risk_score: float,
        oversight_mode: str,
        executed_at: datetime.datetime | None = None,
        trace_id: str | None = None,
    ) -> HOTLRecord:
        """Handle a just-executed HOTL action: notify reviewer + open override window."""
        executed_at = executed_at or _utcnow()

        # Open the override window first so an override cannot race ahead of it.
        record = self._override.register_executed_action(
            action_id=action_id,
            agent_id=agent_id,
            action_type=action_type,
            parameters=parameters,
            risk_score=risk_score,
            executed_at=executed_at,
            trace_id=trace_id,
        )

        # Deliver the reviewer notification (best-effort; failure is audited).
        notification_error: str | None = None
        if self._notifier is not None:
            try:
                await self._notifier(record)
            except Exception as exc:  # notification delivery failure must not crash the flow
                notification_error = str(exc)
                logger.error("hotl_monitor.notify_failed", action_id=action_id, error=str(exc))

        sent_at = _utcnow()
        latency = (sent_at - executed_at).total_seconds()
        within_slo = latency <= self._slo and notification_error is None

        await self._audit.log_event(
            AuditEvent(
                event_type=EVENT_NOTIFICATION_SENT,
                agent_id=agent_id,
                action=action_type,
                outcome="NOTIFIED" if within_slo else "NOTIFICATION_SLO_BREACH",
                risk_score=risk_score,
                metadata={
                    "action_id": action_id,
                    "oversight_mode": oversight_mode,
                    "notification_latency_seconds": round(latency, 3),
                    "notification_slo_seconds": self._slo,
                    "within_slo": within_slo,
                    "override_window_expires_at": record.expires_at.isoformat(),
                    **({"notification_error": notification_error} if notification_error else {}),
                },
                trace_id=trace_id,
            )
        )

        if not within_slo:
            logger.warning(
                "hotl_monitor.notification_slo_breach",
                action_id=action_id,
                latency_seconds=round(latency, 3),
                slo_seconds=self._slo,
            )

        return record

    def notification_within_slo(
        self, executed_at: datetime.datetime, notified_at: datetime.datetime
    ) -> bool:
        """Return True if the notification latency is within the SLO (drift check)."""
        return (notified_at - executed_at).total_seconds() <= self._slo
