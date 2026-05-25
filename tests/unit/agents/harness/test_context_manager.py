"""Unit tests for src/agents/harness/context_manager.py.

Spec: specs/ai/harness-design.md §3 (Context Management Strategy)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.
"""

from __future__ import annotations

from src.agents.harness.context_manager import ContextManager
from src.agents.harness.models import ContextSnapshot


class TestShouldReset:
    def test_returns_true_at_threshold(self) -> None:
        mgr = ContextManager(reset_threshold=0.85)
        assert mgr.should_reset(0.85) is True

    def test_returns_true_above_threshold(self) -> None:
        mgr = ContextManager(reset_threshold=0.85)
        assert mgr.should_reset(0.99) is True

    def test_returns_false_below_threshold(self) -> None:
        mgr = ContextManager(reset_threshold=0.85)
        assert mgr.should_reset(0.84) is False

    def test_returns_false_at_zero(self) -> None:
        mgr = ContextManager(reset_threshold=0.85)
        assert mgr.should_reset(0.0) is False

    def test_threshold_above_one_never_resets(self) -> None:
        mgr = ContextManager(reset_threshold=1.01)
        assert mgr.should_reset(1.0) is False

    def test_custom_threshold_respected(self) -> None:
        mgr = ContextManager(reset_threshold=0.70)
        assert mgr.should_reset(0.70) is True
        assert mgr.should_reset(0.69) is False


class TestCreateSnapshot:
    def test_snapshot_fields_populated(self) -> None:
        mgr = ContextManager()
        snapshot = mgr.create_snapshot(
            agent_id="generator-v1",
            task_id="task-001",
            masked_state={"stage": "sprint-2"},
            key_decisions=["chose React", "used SQLite"],
            last_sprint_id="sprint-001",
        )

        assert snapshot.agent_id == "generator-v1"
        assert snapshot.task_id == "task-001"
        assert snapshot.last_sprint_id == "sprint-001"
        assert "chose React" in snapshot.key_decisions
        assert snapshot.masked_state["stage"] == "sprint-2"

    def test_created_at_is_iso8601(self) -> None:
        mgr = ContextManager()
        snapshot = mgr.create_snapshot(
            agent_id="a",
            task_id="t",
            masked_state={},
        )
        # ISO8601 UTC strings contain 'T' and end with '+00:00' or 'Z'
        assert "T" in snapshot.created_at

    def test_key_decisions_capped_at_20(self) -> None:
        mgr = ContextManager()
        decisions = [f"decision-{i}" for i in range(30)]
        snapshot = mgr.create_snapshot(
            agent_id="a",
            task_id="t",
            masked_state={},
            key_decisions=decisions,
        )
        assert len(snapshot.key_decisions) <= 20

    def test_each_decision_capped_at_200_chars(self) -> None:
        mgr = ContextManager()
        long_decision = "x" * 500
        snapshot = mgr.create_snapshot(
            agent_id="a",
            task_id="t",
            masked_state={},
            key_decisions=[long_decision],
        )
        assert all(len(d) <= 200 for d in snapshot.key_decisions)

    def test_pii_safety_net_applied_to_masked_state(self) -> None:
        mgr = ContextManager()
        # Synthetic email in state — should be masked by safety-net pass
        snapshot = mgr.create_snapshot(
            agent_id="a",
            task_id="t",
            masked_state={"contact": "fake@example.com"},
        )
        assert "fake@example.com" not in str(snapshot.masked_state)

    def test_empty_decisions_allowed(self) -> None:
        mgr = ContextManager()
        snapshot = mgr.create_snapshot(agent_id="a", task_id="t", masked_state={})
        assert snapshot.key_decisions == []

    def test_returns_context_snapshot_instance(self) -> None:
        mgr = ContextManager()
        snapshot = mgr.create_snapshot(agent_id="a", task_id="t", masked_state={})
        assert isinstance(snapshot, ContextSnapshot)


class TestRestorePrompt:
    def test_prompt_contains_task_id(self) -> None:
        mgr = ContextManager()
        snapshot = ContextSnapshot(
            agent_id="gen",
            created_at="2026-05-24T00:00:00+00:00",
            task_id="task-xyz",
            last_sprint_id="sprint-3",
            key_decisions=["used Postgres"],
            masked_state={"step": "act"},
        )
        prompt = mgr.restore_prompt(snapshot)
        assert "task-xyz" in prompt

    def test_prompt_contains_last_sprint(self) -> None:
        mgr = ContextManager()
        snapshot = ContextSnapshot(
            agent_id="gen",
            created_at="2026-05-24T00:00:00+00:00",
            task_id="t",
            last_sprint_id="sprint-7",
            key_decisions=[],
            masked_state={},
        )
        prompt = mgr.restore_prompt(snapshot)
        assert "sprint-7" in prompt

    def test_prompt_contains_key_decisions(self) -> None:
        mgr = ContextManager()
        snapshot = ContextSnapshot(
            agent_id="gen",
            created_at="2026-05-24T00:00:00+00:00",
            task_id="t",
            last_sprint_id=None,
            key_decisions=["chose FastAPI", "added Redis cache"],
            masked_state={},
        )
        prompt = mgr.restore_prompt(snapshot)
        assert "chose FastAPI" in prompt
        assert "added Redis cache" in prompt

    def test_prompt_no_last_sprint_shows_none(self) -> None:
        mgr = ContextManager()
        snapshot = ContextSnapshot(
            agent_id="gen",
            created_at="2026-05-24T00:00:00+00:00",
            task_id="t",
            last_sprint_id=None,
            key_decisions=[],
            masked_state={},
        )
        prompt = mgr.restore_prompt(snapshot)
        assert "none" in prompt.lower()
