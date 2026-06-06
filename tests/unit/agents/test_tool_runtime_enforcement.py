"""Unit tests for ToolExecutor 10-step runtime enforcement.

ADR-0053, ADR-0048 — tool registry enforced at every execution path.
Unregistered tools are blocked. Sandbox-required tools cannot execute directly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.tool_executor import (
    SandboxBypassAttemptError,
    ToolExecutor,
    ToolNotRegisteredError,
    ToolPermissionDeniedError,
)
from src.agents.tool_registry import (
    ExecutionMode,
    ToolDefinition,
    ToolRegistry,
)
from src.guardrails.audit_logger import AuditLogger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_audit() -> AuditLogger:
    audit = MagicMock(spec=AuditLogger)
    audit.log_event = AsyncMock()
    return audit


def _registry_with(*tools: ToolDefinition) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


def _low_risk_direct() -> ToolDefinition:
    return ToolDefinition(
        name="read-db-record",
        description="Read a DB record",
        version="1.0",
        risk_level="low",
        pii_access=[],
        requires_hitl=False,
        rate_limit_per_minute=60,
        rate_limit_per_hour=3600,
        owner_team="platform",
        adr_reference="ADR-0048",
    )


def _high_risk_hitl() -> ToolDefinition:
    return ToolDefinition(
        name="send-email",
        description="Send an email",
        version="1.0",
        risk_level="high",
        pii_access=["L1", "L2"],
        requires_hitl=True,
        rate_limit_per_minute=10,
        rate_limit_per_hour=100,
        owner_team="comms",
        adr_reference="ADR-0048",
    )


def _sandbox_tool() -> ToolDefinition:
    return ToolDefinition(
        name="execute-code",
        description="Execute sandboxed code",
        version="1.0",
        risk_level="high",
        pii_access=[],
        requires_hitl=True,
        execution_mode=ExecutionMode.SANDBOX,
        rate_limit_per_minute=5,
        rate_limit_per_hour=30,
        owner_team="platform",
        adr_reference="ADR-0016",
    )


# ---------------------------------------------------------------------------
# Step 2: Unregistered tool is blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unregistered_tool_is_blocked():
    executor = ToolExecutor(audit_logger=_mock_audit(), registry=ToolRegistry())
    with pytest.raises(ToolNotRegisteredError, match="not registered"):
        await executor.execute(
            action_type="unknown-tool",
            parameters={},
            autonomy_level="full",
            agent_id="test-agent",
        )


@pytest.mark.asyncio
async def test_unregistered_tool_emits_audit_record():
    audit = _mock_audit()
    executor = ToolExecutor(audit_logger=audit, registry=ToolRegistry())
    with pytest.raises(ToolNotRegisteredError):
        await executor.execute(
            action_type="ghost-tool", parameters={}, autonomy_level="full", agent_id="a1"
        )
    audit.log_event.assert_called_once()
    call_args = audit.log_event.call_args[0][0]
    assert call_args.outcome == "BLOCKED_UNREGISTERED"


# ---------------------------------------------------------------------------
# Step 4: requires_hitl=True returns HITL_REQUIRED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hitl_required_tool_returns_hitl_required_outcome():
    reg = _registry_with(_high_risk_hitl())
    executor = ToolExecutor(audit_logger=_mock_audit(), registry=reg)
    result = await executor.execute(
        action_type="send-email",
        parameters={},
        autonomy_level="full",
        agent_id="a1",
    )
    assert result.outcome == "HITL_REQUIRED"
    assert result.hitl_required is True


@pytest.mark.asyncio
async def test_hitl_required_tool_does_not_execute():
    reg = _registry_with(_high_risk_hitl())
    audit = _mock_audit()
    executor = ToolExecutor(audit_logger=audit, registry=reg)
    await executor.execute(
        action_type="send-email", parameters={}, autonomy_level="full", agent_id="a1"
    )
    # No pre-execution or post-execution audit beyond blocking check
    call_outcomes = [c[0][0].outcome for c in audit.log_event.call_args_list]
    assert "EXECUTING" not in call_outcomes
    assert "EXECUTED" not in call_outcomes


# ---------------------------------------------------------------------------
# Step 5: Permission denied when autonomy level is insufficient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_medium_risk_tool_blocked_for_low_autonomy():
    medium_tool = ToolDefinition(
        name="write-db-record",
        description="Write a DB record",
        version="1.0",
        risk_level="medium",
        pii_access=[],
        requires_hitl=False,
        rate_limit_per_minute=20,
        rate_limit_per_hour=200,
        owner_team="platform",
        adr_reference="ADR-0048",
    )
    reg = _registry_with(medium_tool)
    executor = ToolExecutor(audit_logger=_mock_audit(), registry=reg)
    with pytest.raises(ToolPermissionDeniedError, match=r"[Aa]utonomy level"):
        await executor.execute(
            action_type="write-db-record",
            parameters={},
            autonomy_level="read-only",
            agent_id="a1",
        )


# ---------------------------------------------------------------------------
# Step 6: Sandbox bypass is blocked when no sandbox configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sandbox_tool_blocked_without_sandbox_executor():
    sandbox_tool = ToolDefinition(
        name="execute-code",
        description="Execute code",
        version="1.0",
        risk_level="high",
        pii_access=[],
        requires_hitl=False,  # bypassing HITL to test sandbox enforcement
        execution_mode=ExecutionMode.SANDBOX,
        rate_limit_per_minute=5,
        rate_limit_per_hour=30,
        owner_team="platform",
        adr_reference="ADR-0016",
    )
    reg = _registry_with(sandbox_tool)
    executor = ToolExecutor(audit_logger=_mock_audit(), registry=reg, sandbox_executor=None)
    with pytest.raises(SandboxBypassAttemptError, match="SANDBOX"):
        await executor.execute(
            action_type="execute-code",
            parameters={},
            autonomy_level="full",
            agent_id="a1",
        )


# ---------------------------------------------------------------------------
# Steps 8+9: Audit records emitted for successful execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_execution_emits_pre_and_post_audit():
    reg = _registry_with(_low_risk_direct())
    audit = _mock_audit()
    executor = ToolExecutor(audit_logger=audit, registry=reg)
    result = await executor.execute(
        action_type="read-db-record",
        parameters={},
        autonomy_level="full",
        agent_id="a1",
    )
    assert result.outcome == "EXECUTED"
    outcomes = [c[0][0].event_type for c in audit.log_event.call_args_list]
    assert "agent.action.executing" in outcomes
    assert "agent.action.executed" in outcomes


# ---------------------------------------------------------------------------
# Step 10: Failure audit emitted on execution error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_failure_emits_failure_audit():
    audit = _mock_audit()

    broken_sandbox = MagicMock()
    broken_sandbox.execute = AsyncMock(side_effect=RuntimeError("boom"))

    # Make the tool require sandbox so we route through sandbox_executor
    sandbox_tool = ToolDefinition(
        name="read-db-record",
        description="Reads",
        version="1.0",
        risk_level="low",
        pii_access=[],
        requires_hitl=False,
        execution_mode=ExecutionMode.SANDBOX,
        rate_limit_per_minute=60,
        rate_limit_per_hour=3600,
        owner_team="platform",
        adr_reference="ADR-0048",
    )
    reg2 = _registry_with(sandbox_tool)
    executor = ToolExecutor(audit_logger=audit, registry=reg2, sandbox_executor=broken_sandbox)
    result = await executor.execute(
        action_type="read-db-record",
        parameters={},
        autonomy_level="full",
        agent_id="a1",
    )
    assert result.outcome == "FAILED"
    event_types = [c[0][0].event_type for c in audit.log_event.call_args_list]
    assert "agent.action.failed" in event_types


# ---------------------------------------------------------------------------
# Normalization: underscores converted to hyphens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_underscore_action_name_normalized_to_hyphen():
    reg = _registry_with(_low_risk_direct())
    executor = ToolExecutor(audit_logger=_mock_audit(), registry=reg)
    # "read_db_record" should resolve to "read-db-record"
    result = await executor.execute(
        action_type="read_db_record",
        parameters={},
        autonomy_level="full",
        agent_id="a1",
    )
    assert result.outcome == "EXECUTED"
