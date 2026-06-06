"""Unit tests for SubAgentRegistry.

Spec: specs/ai/sub-agent-specialization.md
ADR:  ADR-0032 (Sub-Agent Specialization Registry)
"""

from __future__ import annotations

import pytest

from src.agents.harness.sub_agent_registry import (
    AgentConfig,
    SubAgentRegistry,
    default_registry,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _cfg(name: str, risk: str = "low", require_hitl: bool = False) -> AgentConfig:
    return AgentConfig(
        name=name,
        role=f"Role for {name}",
        system_prompt_template="Do {{task}}.",
        tool_set=["read_file"],
        risk_level=risk,  # type: ignore[arg-type]
        require_hitl=require_hitl,
    )


def _fresh() -> SubAgentRegistry:
    """Return an empty registry (no built-ins)."""
    return SubAgentRegistry()


# ── register() ────────────────────────────────────────────────────────────────


class TestRegister:
    def test_registers_new_agent(self):
        reg = _fresh()
        cfg = _cfg("analyst")
        reg.register("analyst", cfg)
        assert len(reg) == 1

    def test_raises_on_duplicate_name(self):
        reg = _fresh()
        reg.register("analyst", _cfg("analyst"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register("analyst", _cfg("analyst"))

    def test_raises_when_key_mismatches_config_name(self):
        reg = _fresh()
        with pytest.raises(ValueError, match="must match"):
            reg.register("other-name", _cfg("analyst"))

    def test_multiple_agents_registered_independently(self):
        reg = _fresh()
        reg.register("a", _cfg("a"))
        reg.register("b", _cfg("b"))
        assert len(reg) == 2


# ── get() ─────────────────────────────────────────────────────────────────────


class TestGet:
    def test_returns_registered_config(self):
        reg = _fresh()
        cfg = _cfg("checker", risk="high", require_hitl=True)
        reg.register("checker", cfg)
        result = reg.get("checker")
        assert result.name == "checker"
        assert result.risk_level == "high"

    def test_raises_key_error_for_unknown_name(self):
        reg = _fresh()
        with pytest.raises(KeyError, match="not registered"):
            reg.get("ghost")

    def test_key_error_message_lists_available(self):
        reg = _fresh()
        reg.register("alpha", _cfg("alpha"))
        with pytest.raises(KeyError, match="alpha"):
            reg.get("beta")


# ── list_by_risk_level() ──────────────────────────────────────────────────────


class TestListByRiskLevel:
    def test_returns_only_matching_level(self):
        reg = _fresh()
        reg.register("low-a", _cfg("low-a", risk="low"))
        reg.register("low-b", _cfg("low-b", risk="low"))
        reg.register("high-a", _cfg("high-a", risk="high"))

        results = reg.list_by_risk_level("low")
        assert len(results) == 2
        assert all(c.risk_level == "low" for c in results)

    def test_returns_empty_list_for_unregistered_level(self):
        reg = _fresh()
        reg.register("low-a", _cfg("low-a", risk="low"))
        assert reg.list_by_risk_level("critical") == []

    def test_high_risk_agents_listed_correctly(self):
        reg = _fresh()
        reg.register("sec", _cfg("sec", risk="high"))
        results = reg.list_by_risk_level("high")
        assert results[0].name == "sec"


# ── all() ─────────────────────────────────────────────────────────────────────


class TestAll:
    def test_returns_all_registered(self):
        reg = _fresh()
        reg.register("x", _cfg("x"))
        reg.register("y", _cfg("y"))
        assert len(reg.all()) == 2

    def test_returns_copy_not_internal_dict_values(self):
        reg = _fresh()
        reg.register("x", _cfg("x"))
        snapshot = reg.all()
        reg.register("y", _cfg("y"))
        assert len(snapshot) == 1  # snapshot unaffected by later registration


# ── unregister() ──────────────────────────────────────────────────────────────


class TestUnregister:
    def test_removes_registered_agent(self):
        reg = _fresh()
        reg.register("temp", _cfg("temp"))
        reg.unregister("temp")
        assert len(reg) == 0

    def test_no_error_on_missing_name(self):
        reg = _fresh()
        reg.unregister("nonexistent")  # must not raise


# ── default_registry (built-ins) ─────────────────────────────────────────────


class TestDefaultRegistry:
    def test_security_reviewer_registered(self):
        cfg = default_registry.get("security-reviewer")
        assert cfg.risk_level == "high"
        assert cfg.require_hitl is True

    def test_document_generator_registered(self):
        cfg = default_registry.get("document-generator")
        assert cfg.risk_level == "low"
        assert cfg.require_hitl is False

    def test_two_built_ins_present(self):
        assert len(default_registry) >= 2

    def test_high_risk_list_includes_security_reviewer(self):
        high = default_registry.list_by_risk_level("high")
        names = [c.name for c in high]
        assert "security-reviewer" in names

    def test_low_risk_list_includes_document_generator(self):
        low = default_registry.list_by_risk_level("low")
        names = [c.name for c in low]
        assert "document-generator" in names
