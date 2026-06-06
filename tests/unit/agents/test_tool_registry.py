"""Unit tests for ToolRegistry — governed tool registry (specs/ai/tool-registry.md, ADR-0039).

Issue: #16
"""

from __future__ import annotations

import pytest

from src.agents.tool_registry import (
    PIILevel,
    ToolDefinition,
    ToolRegistry,
    ToolRiskLevel,
    UnregisteredToolError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _tool(
    name: str = "test-tool",
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW,
    requires_hitl: bool = False,
    pii_access: list[PIILevel] | None = None,
    version: str = "1.0",
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="A test tool",
        version=version,
        risk_level=risk_level,
        pii_access=pii_access or [PIILevel.L4],
        requires_hitl=requires_hitl,
        rate_limit_per_minute=10,
        rate_limit_per_hour=100,
        owner_team="test-team",
    )


# ── TestRegister ──────────────────────────────────────────────────────────────


class TestRegister:
    def test_register_adds_tool(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("my-tool"))
        assert reg.get("my-tool").name == "my-tool"

    def test_register_duplicate_raises(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("dup-tool"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_tool("dup-tool"))

    def test_register_multiple_different_tools(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("tool-a"))
        reg.register(_tool("tool-b"))
        assert len(reg.all()) == 2


# ── TestGet ───────────────────────────────────────────────────────────────────


class TestGet:
    def test_get_returns_correct_tool(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("find-me"))
        t = reg.get("find-me")
        assert t.name == "find-me"

    def test_get_unknown_raises_key_error(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get("ghost-tool")


# ── TestUnregister ────────────────────────────────────────────────────────────


class TestUnregister:
    def test_unregister_removes_tool(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("remove-me"))
        reg.unregister("remove-me")
        with pytest.raises(KeyError):
            reg.get("remove-me")

    def test_unregister_unknown_raises(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nobody")


# ── TestCheckPermission ───────────────────────────────────────────────────────


class TestCheckPermission:
    def test_requires_hitl_always_permitted(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("hitl-tool", requires_hitl=True, risk_level=ToolRiskLevel.HIGH))
        assert reg.check_permission("hitl-tool", "none") is True

    def test_low_risk_permitted_at_low_risk_level(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("low-tool", risk_level=ToolRiskLevel.LOW, requires_hitl=False))
        assert reg.check_permission("low-tool", "low-risk") is True

    def test_low_risk_permitted_at_full(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("low-tool", risk_level=ToolRiskLevel.LOW, requires_hitl=False))
        assert reg.check_permission("low-tool", "full") is True

    def test_medium_risk_not_permitted_at_low_risk(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("med-tool", risk_level=ToolRiskLevel.MEDIUM, requires_hitl=False))
        assert reg.check_permission("med-tool", "low-risk") is False

    def test_medium_risk_permitted_at_medium_risk(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("med-tool", risk_level=ToolRiskLevel.MEDIUM, requires_hitl=False))
        assert reg.check_permission("med-tool", "medium-risk") is True

    def test_high_risk_permitted_only_at_full(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("high-tool", risk_level=ToolRiskLevel.HIGH, requires_hitl=False))
        assert reg.check_permission("high-tool", "full") is True
        assert reg.check_permission("high-tool", "medium-risk") is False
        assert reg.check_permission("high-tool", "none") is False

    def test_unknown_tool_raises(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.check_permission("ghost", "full")


# ── TestListByRisk ────────────────────────────────────────────────────────────


class TestListByRisk:
    def test_list_by_risk_returns_matching(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("low-1", risk_level=ToolRiskLevel.LOW))
        reg.register(_tool("low-2", risk_level=ToolRiskLevel.LOW))
        reg.register(_tool("high-1", risk_level=ToolRiskLevel.HIGH))
        low = reg.list_by_risk("low")
        assert len(low) == 2
        assert all(t.risk_level == ToolRiskLevel.LOW for t in low)

    def test_list_by_risk_empty_when_none_match(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("low-1", risk_level=ToolRiskLevel.LOW))
        assert reg.list_by_risk("high") == []


# ── TestAssertRegistered ──────────────────────────────────────────────────────


class TestAssertRegistered:
    def test_returns_tool_when_registered(self) -> None:
        reg = ToolRegistry()
        reg.register(_tool("ok-tool"))
        t = reg.assert_registered("ok-tool")
        assert t.name == "ok-tool"

    def test_raises_unregistered_error_when_missing(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(UnregisteredToolError, match="unregistered tool"):
            reg.assert_registered("missing-tool")


# ── TestDefaultRegistry ───────────────────────────────────────────────────────


class TestDefaultRegistry:
    def test_default_registry_has_starter_tools(self) -> None:
        from src.agents.tool_registry import default_tool_registry

        names = {t.name for t in default_tool_registry.all()}
        assert "send-email" in names
        assert "read-db-record" in names
        assert "write-db-record" in names

    def test_send_email_requires_hitl(self) -> None:
        from src.agents.tool_registry import default_tool_registry

        assert default_tool_registry.get("send-email").requires_hitl is True

    def test_read_db_record_is_low_risk(self) -> None:
        from src.agents.tool_registry import default_tool_registry

        assert default_tool_registry.get("read-db-record").risk_level == ToolRiskLevel.LOW
