"""Unit tests for HOTLMonitor — notification SLO + override window opening.

ADR-0055 — HOTL actions notify the reviewer within the SLO and open an override window.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.compensation_registry import CompensationRegistry
from src.agents.hotl_monitor import EVENT_NOTIFICATION_SENT, HOTLMonitor
from src.agents.override_service import OverrideService
from src.agents.tool_registry import ToolDefinition, ToolRegistry, ToolRiskLevel
from src.guardrails.audit_logger import AuditLogger


def _audit() -> MagicMock:
    audit = MagicMock(spec=AuditLogger)
    audit.log_event = AsyncMock()
    return audit


def _comp_registry() -> CompensationRegistry:
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="read-db-record",
            description="read",
            version="1.0",
            risk_level=ToolRiskLevel.LOW,
            pii_access=[],
            requires_hitl=False,
            rate_limit_per_minute=60,
            rate_limit_per_hour=1000,
            owner_team="platform",
            reversible=True,
            max_hotl_risk_score=0.3,
        )
    )
    return CompensationRegistry(registry=reg)


def _monitor(audit, *, slo=60, notifier=None):
    override = OverrideService(audit_logger=audit, compensation_registry=_comp_registry())
    return HOTLMonitor(
        audit_logger=audit,
        override_service=override,
        notification_slo_seconds=slo,
        notifier=notifier,
    ), override


@pytest.mark.asyncio
async def test_notification_emitted_and_window_opened():
    audit = _audit()
    monitor, override = _monitor(audit)

    record = await monitor.on_hotl_executed(
        action_id="act-1",
        agent_id="agent-1",
        action_type="read-db-record",
        parameters={},
        risk_score=0.1,
        oversight_mode="HOTL_LOW_RISK",
    )

    # Override window registered.
    assert override.get("act-1").status == "ACTIVE"
    assert record.expires_at > record.executed_at

    # Notification audit event emitted within SLO.
    notif = next(
        c[0][0]
        for c in audit.log_event.call_args_list
        if c[0][0].event_type == EVENT_NOTIFICATION_SENT
    )
    assert notif.outcome == "NOTIFIED"
    assert notif.metadata["within_slo"] is True


@pytest.mark.asyncio
async def test_notifier_called():
    audit = _audit()
    notifier = AsyncMock()
    monitor, _ = _monitor(audit, notifier=notifier)

    await monitor.on_hotl_executed(
        action_id="act-2",
        agent_id="agent-1",
        action_type="read-db-record",
        parameters={},
        risk_score=0.1,
        oversight_mode="HOTL_LOW_RISK",
    )
    notifier.assert_awaited_once()


@pytest.mark.asyncio
async def test_notifier_failure_marks_slo_breach_but_does_not_raise():
    audit = _audit()
    notifier = AsyncMock(side_effect=RuntimeError("pager down"))
    monitor, _ = _monitor(audit, notifier=notifier)

    # Must not raise even though the notifier failed.
    await monitor.on_hotl_executed(
        action_id="act-3",
        agent_id="agent-1",
        action_type="read-db-record",
        parameters={},
        risk_score=0.1,
        oversight_mode="HOTL_LOW_RISK",
    )
    notif = next(
        c[0][0]
        for c in audit.log_event.call_args_list
        if c[0][0].event_type == EVENT_NOTIFICATION_SENT
    )
    assert notif.outcome == "NOTIFICATION_SLO_BREACH"
    assert notif.metadata["within_slo"] is False
    assert "notification_error" in notif.metadata


def test_notification_within_slo_helper():
    audit = _audit()
    monitor, _ = _monitor(audit, slo=60)
    t0 = datetime.datetime(2026, 6, 6, 12, 0, 0, tzinfo=datetime.UTC)
    assert monitor.notification_within_slo(t0, t0 + datetime.timedelta(seconds=30)) is True
    assert monitor.notification_within_slo(t0, t0 + datetime.timedelta(seconds=90)) is False
