"""Unit tests for groundedness SLI metrics in src/observability/metrics.py.

Spec: docs/ai/eval-scorecard.md · docs/ai/ai-observability-naming.md | ADR: ADR-0080
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge

# ── helpers ───────────────────────────────────────────────────────────────────


def _fresh_metrics():
    """Return isolated metric instances on a private registry to avoid global pollution."""
    registry = CollectorRegistry()
    score = Gauge(
        "agent_groundedness_score_test",
        "Groundedness score",
        ["agent_id", "sprint_id"],
        registry=registry,
    )
    flagged = Counter(
        "agent_hallucination_flagged_test",
        "Hallucination flagged",
        ["agent_id", "sprint_id"],
        registry=registry,
    )
    return registry, score, flagged


# ── groundedness score gauge ──────────────────────────────────────────────────


class TestGroundednessScoreMetric:
    def test_score_set_records_value(self) -> None:
        _, score, _ = _fresh_metrics()
        score.labels("planner", "s1").set(0.9)
        assert score.labels("planner", "s1")._value.get() == 0.9

    def test_score_can_be_updated(self) -> None:
        _, score, _ = _fresh_metrics()
        score.labels("planner", "s1").set(1.0)
        score.labels("planner", "s1").set(0.5)
        assert score.labels("planner", "s1")._value.get() == 0.5

    def test_different_agents_isolated(self) -> None:
        _, score, _ = _fresh_metrics()
        score.labels("planner", "s1").set(0.8)
        score.labels("generator", "s1").set(0.3)
        assert score.labels("planner", "s1")._value.get() == 0.8
        assert score.labels("generator", "s1")._value.get() == 0.3


# ── hallucination flagged counter ─────────────────────────────────────────────


class TestHallucinationFlaggedMetric:
    def test_counter_increments(self) -> None:
        _, _, flagged = _fresh_metrics()
        flagged.labels("planner", "s1").inc()
        assert flagged.labels("planner", "s1")._value.get() == 1.0

    def test_counter_accumulates(self) -> None:
        _, _, flagged = _fresh_metrics()
        flagged.labels("planner", "s1").inc()
        flagged.labels("planner", "s1").inc()
        assert flagged.labels("planner", "s1")._value.get() == 2.0


# ── record_groundedness helper ────────────────────────────────────────────────


class TestRecordGroundednessHelper:
    def test_helper_exists_and_is_callable(self) -> None:
        from src.observability.metrics import record_groundedness

        assert callable(record_groundedness)

    def test_helper_sets_score_and_does_not_flag_when_grounded(self) -> None:
        from src.observability.metrics import (
            AGENT_GROUNDEDNESS_SCORE,
            AGENT_HALLUCINATION_FLAGGED_COUNTER,
            record_groundedness,
        )

        before = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("agent_grounded", "sp")._value.get()
        record_groundedness(0.95, flagged=False, agent_id="agent_grounded", sprint_id="sp")
        assert AGENT_GROUNDEDNESS_SCORE.labels("agent_grounded", "sp")._value.get() == 0.95
        after = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("agent_grounded", "sp")._value.get()
        assert after == before  # not flagged → counter unchanged

    def test_helper_increments_flag_when_hallucinated(self) -> None:
        from src.observability.metrics import (
            AGENT_GROUNDEDNESS_SCORE,
            AGENT_HALLUCINATION_FLAGGED_COUNTER,
            record_groundedness,
        )

        before = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("agent_halluc", "sp")._value.get()
        record_groundedness(0.2, flagged=True, agent_id="agent_halluc", sprint_id="sp")
        assert AGENT_GROUNDEDNESS_SCORE.labels("agent_halluc", "sp")._value.get() == 0.2
        after = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("agent_halluc", "sp")._value.get()
        assert after == before + 1.0

    def test_helper_uses_default_labels(self) -> None:
        from src.observability.metrics import record_groundedness

        # Should not raise when labels are omitted (defaults applied).
        record_groundedness(0.8, flagged=False)
