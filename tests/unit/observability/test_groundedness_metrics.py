"""Unit tests for the groundedness SLI metrics (ADR-0080).

Spec:  docs/ai/eval-scorecard.md (groundedness rubric)
       docs/ai/ai-observability-naming.md (reserved metric names + prompt_version label)

Covers `record_groundedness_score` and the two reserved metrics it drives:
`agent_retrieval_grounding_ratio` (gauge) and `agent_hallucination_flagged_total`
(counter), both labelled by `prompt_version`.

All data here is synthetic. No real personal data appears in this file.
"""

from __future__ import annotations

import pytest

from src.observability.metrics import (
    AGENT_HALLUCINATION_FLAGGED_COUNTER,
    AGENT_RETRIEVAL_GROUNDING_RATIO,
    record_groundedness_score,
)

_PV = "harness.evaluator@2.0"


@pytest.mark.unit
class TestGroundednessMetrics:
    def test_reserved_metric_names(self) -> None:
        assert AGENT_RETRIEVAL_GROUNDING_RATIO._name == "agent_retrieval_grounding_ratio"
        # prometheus_client strips the _total suffix off the stored name.
        assert AGENT_HALLUCINATION_FLAGGED_COUNTER._name == "agent_hallucination_flagged"

    def test_prompt_version_is_a_label(self) -> None:
        assert "prompt_version" in AGENT_RETRIEVAL_GROUNDING_RATIO._labelnames
        assert "prompt_version" in AGENT_HALLUCINATION_FLAGGED_COUNTER._labelnames

    def test_records_grounding_ratio_gauge(self) -> None:
        record_groundedness_score("evaluator", _PV, 0.82, flagged=False)
        value = AGENT_RETRIEVAL_GROUNDING_RATIO.labels("evaluator", _PV)._value.get()
        assert value == pytest.approx(0.82)

    def test_flagged_increments_hallucination_counter(self) -> None:
        pv = "test.flagged@1.0"
        before = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("evaluator", pv)._value.get()
        record_groundedness_score("evaluator", pv, 0.3, flagged=True)
        after = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("evaluator", pv)._value.get()
        assert after == before + 1

    def test_not_flagged_does_not_increment_counter(self) -> None:
        pv = "test.clean@1.0"
        before = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("evaluator", pv)._value.get()
        record_groundedness_score("evaluator", pv, 0.95, flagged=False)
        after = AGENT_HALLUCINATION_FLAGGED_COUNTER.labels("evaluator", pv)._value.get()
        assert after == before

    def test_ratio_clamped_to_unit_interval(self) -> None:
        record_groundedness_score("evaluator", "test.clamp.hi@1.0", 1.7, flagged=False)
        record_groundedness_score("evaluator", "test.clamp.lo@1.0", -0.5, flagged=False)
        hi = AGENT_RETRIEVAL_GROUNDING_RATIO.labels("evaluator", "test.clamp.hi@1.0")._value.get()
        lo = AGENT_RETRIEVAL_GROUNDING_RATIO.labels("evaluator", "test.clamp.lo@1.0")._value.get()
        assert hi == 1.0
        assert lo == 0.0
