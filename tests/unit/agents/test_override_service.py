"""Unit tests for OverrideService — HOTL override window + compensation flow.

ADR-0055 — override window enforced; overrides audited with actor/reason/timestamp;
failed or impossible compensation raises an escalation event.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.compensation_registry import CompensationRegistry
from src.agents.override_service import (
    EVENT_ACTION_CONFIRMED,
    EVENT_COMPENSATION_FAILED,
    EVENT_COMPENSATION_STARTED,
    EVENT_COMPENSATION_SUCCEEDED,
    EVENT_ESCALATION_RAISED,
    EVENT_OVERRIDE_REQUESTED,
    OverrideService,
    OverrideWindowExpiredError,
    UnknownHOTLActionError,
)
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
            name="write-db-record",
            description="write",
            version="1.0",
            risk_level=ToolRiskLevel.MEDIUM,
            pii_access=[],
            requires_hitl=False,
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
            owner_team="platform",
            reversible=True,
            compensating_action="restore-db-record",
            max_hotl_risk_score=0.5,
        )
    )
    reg.register(
        ToolDefinition(
            name="generate-report",
            description="report",
            version="1.0",
            risk_level=ToolRiskLevel.LOW,
            pii_access=[],
            requires_hitl=False,
            rate_limit_per_minute=5,
            rate_limit_per_hour=50,
            owner_team="data",
            reversible=True,
            compensating_action=None,  # reversible but no auto-compensation
            max_hotl_risk_score=0.3,
        )
    )
    return CompensationRegistry(registry=reg)


def _event_types(audit: MagicMock) -> list[str]:
    return [c[0][0].event_type for c in audit.log_event.call_args_list]


def _register(service: OverrideService, *, action_type="write-db-record", action_id="act-1"):
    return service.register_executed_action(
        action_id=action_id,
        agent_id="agent-1",
        action_type=action_type,
        parameters={"record_id": "synthetic-9"},
        risk_score=0.3,
    )


# ── Window enforcement ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_override_within_window_runs_compensation():
    audit = _audit()
    compensator = AsyncMock(return_value={"status": "restored"})
    svc = OverrideService(
        audit_logger=audit,
        compensation_registry=_comp_registry(),
        override_window_seconds=300,
        compensator=compensator,
    )
    _register(svc)

    result = await svc.request_override(action_id="act-1", actor="alice", reason="wrong record")

    assert result.outcome == "COMPENSATED"
    assert result.compensating_action == "restore-db-record"
    assert result.escalated is False
    compensator.assert_awaited_once()
    types = _event_types(audit)
    assert EVENT_OVERRIDE_REQUESTED in types
    assert EVENT_COMPENSATION_STARTED in types
    assert EVENT_COMPENSATION_SUCCEEDED in types


@pytest.mark.asyncio
async def test_override_after_window_is_rejected():
    audit = _audit()
    svc = OverrideService(
        audit_logger=audit,
        compensation_registry=_comp_registry(),
        override_window_seconds=300,
        compensator=AsyncMock(),
    )
    record = _register(svc)
    late = record.expires_at + datetime.timedelta(seconds=1)

    with pytest.raises(OverrideWindowExpiredError):
        await svc.request_override(action_id="act-1", actor="alice", reason="too late", now=late)
    # The override request itself is still audited (actor/reason/timestamp).
    assert EVENT_OVERRIDE_REQUESTED in _event_types(audit)


@pytest.mark.asyncio
async def test_is_within_window():
    svc = OverrideService(audit_logger=_audit(), compensation_registry=_comp_registry())
    record = _register(svc)
    assert svc.is_within_window("act-1", now=record.executed_at) is True
    assert (
        svc.is_within_window("act-1", now=record.expires_at + datetime.timedelta(seconds=1))
        is False
    )


# ── Override request audit content ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_override_request_audited_with_actor_and_reason():
    audit = _audit()
    svc = OverrideService(
        audit_logger=audit,
        compensation_registry=_comp_registry(),
        compensator=AsyncMock(return_value={}),
    )
    _register(svc)
    await svc.request_override(action_id="act-1", actor="bob", reason="duplicate write")

    requested = next(
        c[0][0]
        for c in audit.log_event.call_args_list
        if c[0][0].event_type == EVENT_OVERRIDE_REQUESTED
    )
    assert requested.metadata["actor"] == "bob"
    assert requested.metadata["reason"] == "duplicate write"
    assert "requested_at" in requested.metadata


# ── Compensation failure → escalation ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_compensation_failure_raises_escalation():
    audit = _audit()
    compensator = AsyncMock(side_effect=RuntimeError("downstream 500"))
    svc = OverrideService(
        audit_logger=audit,
        compensation_registry=_comp_registry(),
        compensator=compensator,
    )
    _register(svc)

    result = await svc.request_override(action_id="act-1", actor="alice", reason="bad data")

    assert result.outcome == "COMPENSATION_FAILED"
    assert result.escalated is True
    types = _event_types(audit)
    assert EVENT_COMPENSATION_FAILED in types
    assert EVENT_ESCALATION_RAISED in types


@pytest.mark.asyncio
async def test_no_compensating_action_escalates():
    audit = _audit()
    svc = OverrideService(
        audit_logger=audit,
        compensation_registry=_comp_registry(),
        compensator=AsyncMock(),
    )
    _register(svc, action_type="generate-report", action_id="rep-1")

    result = await svc.request_override(action_id="rep-1", actor="alice", reason="wrong report")

    assert result.outcome == "NO_COMPENSATION"
    assert result.escalated is True
    assert EVENT_ESCALATION_RAISED in _event_types(audit)


@pytest.mark.asyncio
async def test_no_compensator_configured_escalates():
    audit = _audit()
    svc = OverrideService(
        audit_logger=audit,
        compensation_registry=_comp_registry(),
        compensator=None,  # no executor wired
    )
    _register(svc)

    result = await svc.request_override(action_id="act-1", actor="alice", reason="x")
    assert result.outcome == "NO_COMPENSATION"
    assert result.escalated is True


# ── Confirmation ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_emits_confirmed_event():
    audit = _audit()
    svc = OverrideService(audit_logger=audit, compensation_registry=_comp_registry())
    record = _register(svc)

    confirmed = await svc.confirm("act-1", now=record.expires_at + datetime.timedelta(seconds=1))
    assert confirmed.status == "CONFIRMED"
    assert EVENT_ACTION_CONFIRMED in _event_types(audit)


# ── Unknown action ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_override_unknown_action_raises():
    svc = OverrideService(audit_logger=_audit(), compensation_registry=_comp_registry())
    with pytest.raises(UnknownHOTLActionError):
        await svc.request_override(action_id="missing", actor="a", reason="r")
