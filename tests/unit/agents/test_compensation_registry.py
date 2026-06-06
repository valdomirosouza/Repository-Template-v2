"""Unit tests for CompensationRegistry — reversibility + HOTL eligibility.

ADR-0055 — non-reversible actions cannot run autonomously under HOTL.
"""

from __future__ import annotations

import pytest

from src.agents.compensation_registry import CompensationRegistry
from src.agents.tool_registry import (
    ExecutionMode,
    ToolDefinition,
    ToolRegistry,
    ToolRiskLevel,
)


def _reversible_low() -> ToolDefinition:
    return ToolDefinition(
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
        compensating_action=None,
        max_hotl_risk_score=0.3,
        allowed_autonomy_levels=("low-risk", "medium-risk", "full"),
    )


def _reversible_with_comp() -> ToolDefinition:
    return ToolDefinition(
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
        allowed_autonomy_levels=("medium-risk", "full"),
    )


def _non_reversible() -> ToolDefinition:
    return ToolDefinition(
        name="send-email",
        description="email",
        version="1.0",
        risk_level=ToolRiskLevel.HIGH,
        pii_access=[],
        requires_hitl=True,
        execution_mode=ExecutionMode.DIRECT,
        rate_limit_per_minute=2,
        rate_limit_per_hour=20,
        owner_team="platform",
        reversible=False,
        compensating_action=None,
        max_hotl_risk_score=0.0,
        allowed_autonomy_levels=(),
    )


def _registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(_reversible_low())
    reg.register(_reversible_with_comp())
    reg.register(_non_reversible())
    return reg


@pytest.fixture
def comp() -> CompensationRegistry:
    return CompensationRegistry(registry=_registry())


def test_reversible_flag(comp):
    assert comp.is_reversible("read-db-record") is True
    assert comp.is_reversible("send-email") is False


def test_get_compensating_action(comp):
    assert comp.get_compensating_action("write-db-record") == "restore-db-record"
    assert comp.get_compensating_action("read-db-record") is None


def test_has_compensating_action(comp):
    assert comp.has_compensating_action("write-db-record") is True
    assert comp.has_compensating_action("read-db-record") is False


def test_underscore_normalization(comp):
    assert comp.is_reversible("read_db_record") is True


def test_can_run_under_hotl_reversible_within_ceiling(comp):
    allowed, reason = comp.can_run_under_hotl("read-db-record", 0.1)
    assert allowed is True
    assert reason


def test_can_run_under_hotl_reversible_over_ceiling(comp):
    allowed, reason = comp.can_run_under_hotl("read-db-record", 0.9)
    assert allowed is False
    assert "exceeds" in reason


def test_non_reversible_cannot_run_under_hotl(comp):
    allowed, reason = comp.can_run_under_hotl("send-email", 0.0)
    assert allowed is False
    assert "non-reversible" in reason


def test_unregistered_cannot_run_under_hotl(comp):
    allowed, reason = comp.can_run_under_hotl("ghost-tool", 0.0)
    assert allowed is False
    assert "not a registered tool" in reason
