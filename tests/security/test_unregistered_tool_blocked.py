"""Security test: unregistered tools are blocked at runtime.

Verifies that the tool registry enforcement (Step 2 of ToolExecutor)
cannot be bypassed. ADR-0048, ADR-0053.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.tool_executor import ToolExecutor, ToolNotRegisteredError
from src.agents.tool_registry import ToolRegistry
from src.guardrails.audit_logger import AuditLogger


def _mock_audit() -> AuditLogger:
    audit = MagicMock(spec=AuditLogger)
    audit.log_event = AsyncMock()
    return audit


@pytest.mark.security
class TestUnregisteredToolBlocked:
    """Adversarial tests for tool registry bypass attempts."""

    @pytest.mark.asyncio
    async def test_empty_registry_blocks_all_actions(self):
        executor = ToolExecutor(audit_logger=_mock_audit(), registry=ToolRegistry())
        with pytest.raises(ToolNotRegisteredError):
            await executor.execute(
                action_type="any-action", parameters={}, autonomy_level="full", agent_id="attacker"
            )

    @pytest.mark.asyncio
    async def test_sql_injection_in_action_name_blocked(self):
        executor = ToolExecutor(audit_logger=_mock_audit(), registry=ToolRegistry())
        with pytest.raises(ToolNotRegisteredError):
            await executor.execute(
                action_type="'; DROP TABLE tools; --",
                parameters={},
                autonomy_level="full",
                agent_id="attacker",
            )

    @pytest.mark.asyncio
    async def test_path_traversal_in_action_name_blocked(self):
        executor = ToolExecutor(audit_logger=_mock_audit(), registry=ToolRegistry())
        with pytest.raises(ToolNotRegisteredError):
            await executor.execute(
                action_type="../../etc/passwd",
                parameters={},
                autonomy_level="full",
                agent_id="attacker",
            )

    @pytest.mark.asyncio
    async def test_empty_action_name_blocked(self):
        executor = ToolExecutor(audit_logger=_mock_audit(), registry=ToolRegistry())
        with pytest.raises(ToolNotRegisteredError):
            await executor.execute(
                action_type="", parameters={}, autonomy_level="full", agent_id="attacker"
            )

    @pytest.mark.asyncio
    async def test_high_autonomy_does_not_bypass_registry(self):
        """FULL autonomy level must not skip tool registration check."""
        executor = ToolExecutor(audit_logger=_mock_audit(), registry=ToolRegistry())
        with pytest.raises(ToolNotRegisteredError):
            await executor.execute(
                action_type="delete-all-data",
                parameters={},
                autonomy_level="full",
                agent_id="attacker",
            )

    @pytest.mark.asyncio
    async def test_blocked_action_emits_audit_record(self):
        """Blocked attempt must be audited so it appears in the immutable log."""
        audit = _mock_audit()
        executor = ToolExecutor(audit_logger=audit, registry=ToolRegistry())
        with pytest.raises(ToolNotRegisteredError):
            await executor.execute(
                action_type="rogue-action", parameters={}, autonomy_level="full", agent_id="a1"
            )
        audit.log_event.assert_called_once()
        event = audit.log_event.call_args[0][0]
        assert event.outcome == "BLOCKED_UNREGISTERED"
        assert event.risk_score == 1.0
