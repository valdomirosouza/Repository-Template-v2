"""Unit tests for ContextGraph — Autonomy tier (specs/ai/context-graph.md, ADR-0041).

Issue: #18
"""

from __future__ import annotations

import pytest

from src.agents.context_graph import ContextGraph

# ── TestInit ──────────────────────────────────────────────────────────────────


class TestInit:
    def test_creates_with_root_goal(self) -> None:
        g = ContextGraph(session_id="s1", root_description="Migrate API")
        assert g.root_goal.description == "Migrate API"
        assert g.root_goal.status == "active"
        assert g.session_id == "s1"
        assert g.graph_id != ""

    def test_starts_empty(self) -> None:
        g = ContextGraph("s1", "root")
        assert g._sub_goals == {}
        assert g._constraints == []
        assert g._gathered_context == []
        assert g._decisions == []


# ── TestAddSubGoal ────────────────────────────────────────────────────────────


class TestAddSubGoal:
    def test_returns_goal_id(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("step one")
        assert isinstance(gid, str)
        assert len(gid) > 0

    def test_sub_goal_stored(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("step one")
        assert gid in g._sub_goals
        assert g._sub_goals[gid].description == "step one"

    def test_multiple_sub_goals(self) -> None:
        g = ContextGraph("s1", "root")
        ids = [g.add_sub_goal(f"step {i}") for i in range(3)]
        assert len(set(ids)) == 3
        assert len(g._sub_goals) == 3

    def test_sub_goal_parent_is_root(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("child")
        assert g._sub_goals[gid].parent_id == g.root_goal.goal_id


# ── TestMarkComplete ──────────────────────────────────────────────────────────


class TestMarkComplete:
    def test_marks_sub_goal_complete(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("do it")
        g.mark_complete(gid)
        assert g._sub_goals[gid].status == "completed"

    def test_marks_root_complete(self) -> None:
        g = ContextGraph("s1", "root")
        g.mark_complete(g.root_goal.goal_id)
        assert g.root_goal.status == "completed"

    def test_unknown_goal_raises(self) -> None:
        g = ContextGraph("s1", "root")
        with pytest.raises(KeyError):
            g.mark_complete("nonexistent-id")


# ── TestMarkBlocked ───────────────────────────────────────────────────────────


class TestMarkBlocked:
    def test_marks_sub_goal_blocked(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("blocked step")
        g.mark_blocked(gid)
        assert g._sub_goals[gid].status == "blocked"


# ── TestAddConstraint ─────────────────────────────────────────────────────────


class TestAddConstraint:
    def test_stores_constraint(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_constraint("compliance", "no PII in logs")
        assert len(g._constraints) == 1
        assert g._constraints[0].type == "compliance"
        assert g._constraints[0].value == "no PII in logs"

    def test_multiple_constraints(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_constraint("time", "finish by Friday")
        g.add_constraint("resource", "max 2 API calls")
        assert len(g._constraints) == 2


# ── TestAddGatheredContext ────────────────────────────────────────────────────


class TestAddGatheredContext:
    def test_stores_context(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_gathered_context("docs/api.md", "abc123", 0.9)
        assert len(g._gathered_context) == 1
        assert g._gathered_context[0].source == "docs/api.md"
        assert g._gathered_context[0].relevance_score == 0.9


# ── TestAddDecision ───────────────────────────────────────────────────────────


class TestAddDecision:
    def test_returns_decision_id(self) -> None:
        g = ContextGraph("s1", "root")
        did = g.add_decision("Use adapter pattern")
        assert isinstance(did, str) and len(did) > 0

    def test_stores_decision_with_adr(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_decision("Use adapter pattern", adr_reference="ADR-0024")
        assert g._decisions[0].adr_reference == "ADR-0024"

    def test_multiple_decisions(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_decision("Decision A")
        g.add_decision("Decision B")
        assert len(g._decisions) == 2


# ── TestToPromptBlock ─────────────────────────────────────────────────────────


class TestToPromptBlock:
    def test_contains_context_graph_markers(self) -> None:
        g = ContextGraph("s1", "Migrate API")
        block = g.to_prompt_block()
        assert "[CONTEXT_GRAPH]" in block
        assert "[/CONTEXT_GRAPH]" in block

    def test_contains_root_goal(self) -> None:
        g = ContextGraph("s1", "Migrate API")
        block = g.to_prompt_block()
        assert "Migrate API" in block

    def test_shows_completed_sub_goal_with_checkmark(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("Done step")
        g.mark_complete(gid)
        block = g.to_prompt_block()
        assert "✅" in block
        assert "Done step" in block

    def test_shows_blocked_sub_goal(self) -> None:
        g = ContextGraph("s1", "root")
        gid = g.add_sub_goal("Blocked step")
        g.mark_blocked(gid)
        assert "🚫" in g.to_prompt_block()

    def test_shows_constraints(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_constraint("compliance", "no PII")
        assert "no PII" in g.to_prompt_block()

    def test_shows_decisions_with_adr(self) -> None:
        g = ContextGraph("s1", "root")
        g.add_decision("Use adapter", "ADR-0024")
        block = g.to_prompt_block()
        assert "Use adapter" in block
        assert "ADR-0024" in block


# ── TestSerialisation ─────────────────────────────────────────────────────────


class TestSerialisation:
    def test_to_dict_roundtrip(self) -> None:
        g = ContextGraph("s1", "Migrate API")
        gid = g.add_sub_goal("Audit usage")
        g.mark_complete(gid)
        g.add_constraint("time", "by Friday")
        g.add_gathered_context("docs/api.md", "abc", 0.8)
        g.add_decision("Use adapter", "ADR-0024")

        data = g.to_dict()
        g2 = ContextGraph.from_dict(data)

        assert g2.graph_id == g.graph_id
        assert g2.session_id == g.session_id
        assert g2.root_goal.description == "Migrate API"
        assert len(g2._sub_goals) == 1
        assert next(iter(g2._sub_goals.values())).status == "completed"
        assert len(g2._constraints) == 1
        assert len(g2._gathered_context) == 1
        assert len(g2._decisions) == 1

    def test_to_dict_contains_required_keys(self) -> None:
        g = ContextGraph("s1", "root")
        d = g.to_dict()
        for key in (
            "graph_id",
            "session_id",
            "root_goal",
            "sub_goals",
            "constraints",
            "gathered_context",
            "decisions_made",
            "created_at",
            "updated_at",
        ):
            assert key in d


# ── TestAutonomyPrerequisiteError ─────────────────────────────────────────────


class TestAutonomyPrerequisiteError:
    def test_is_runtime_error(self) -> None:
        from src.shared.feature_flags import AutonomyPrerequisiteError

        assert issubclass(AutonomyPrerequisiteError, RuntimeError)
