"""Unit tests for FeedbackLearner — Learn stage (specs/ai/learn-stage.md, ADR-0038).

Issue: #15
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.agents.feedback_learner import (
    FeedbackLearner,
    OutcomeFeedback,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _fb(
    action_type: str = "send-email",
    decision: str = "rejected",
    reason: str = "PII in payload",
    payload_hash: str = "abc123",
    agent_id: str = "agent-1",
) -> OutcomeFeedback:
    return OutcomeFeedback(
        action_type=action_type,
        payload_hash=payload_hash,
        decision=decision,
        decision_reason=reason,
        agent_id=agent_id,
    )


# ── TestRecord ────────────────────────────────────────────────────────────────


class TestRecord:
    def test_record_stores_feedback(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb())
        assert len(learner._store) == 1

    def test_record_multiple(self) -> None:
        learner = FeedbackLearner()
        for _ in range(5):
            learner.record(_fb())
        assert len(learner._store) == 5

    def test_record_sets_timestamp(self) -> None:
        learner = FeedbackLearner()
        before = datetime.now(UTC)
        learner.record(_fb())
        _, ts = learner._store[0]
        assert ts >= before


# ── TestGetSimilarPrecedents ──────────────────────────────────────────────────


class TestGetSimilarPrecedents:
    def test_returns_empty_when_no_records(self) -> None:
        learner = FeedbackLearner()
        result = learner.get_similar_precedents("send-email", "hash1")
        assert result == []

    def test_returns_matching_action_type(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb(action_type="send-email", decision="rejected"))
        learner.record(_fb(action_type="read-db", decision="approved"))
        result = learner.get_similar_precedents("send-email", "hash1")
        assert len(result) == 1
        assert result[0].action_type == "send-email"

    def test_exact_hash_ranked_first(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb(action_type="send-email", payload_hash="other", decision="approved"))
        learner.record(_fb(action_type="send-email", payload_hash="exact", decision="rejected"))
        result = learner.get_similar_precedents("send-email", "exact", n=5)
        assert result[0].decision == "rejected"

    def test_respects_feedback_window(self) -> None:
        learner = FeedbackLearner()
        old_ts = datetime.now(UTC) - timedelta(days=31)
        learner._store.append((_fb(action_type="send-email"), old_ts))
        result = learner.get_similar_precedents("send-email", "hash1")
        assert result == []

    def test_deduplicates_by_action_and_decision(self) -> None:
        learner = FeedbackLearner()
        for _ in range(3):
            learner.record(_fb(action_type="send-email", decision="rejected", reason="PII"))
        result = learner.get_similar_precedents("send-email", "hash1")
        assert len(result) == 1
        assert result[0].occurrences == 3

    def test_respects_n_limit(self) -> None:
        learner = FeedbackLearner()
        for i in range(10):
            learner.record(_fb(action_type=f"action-{i}", decision="rejected"))
        result = learner.get_similar_precedents("action-0", "hash", n=3)
        assert len(result) <= 3


# ── TestBuildPrecedentsBlock ──────────────────────────────────────────────────


class TestBuildPrecedentsBlock:
    def test_returns_none_in_passive_mode(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb())
        result = learner.build_precedents_block("send-email", "hash", mode="passive")
        assert result is None

    def test_returns_none_when_no_precedents(self) -> None:
        learner = FeedbackLearner()
        result = learner.build_precedents_block("send-email", "hash", mode="active")
        assert result is None

    def test_returns_block_in_active_mode(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb(action_type="send-email", decision="rejected", reason="PII in payload"))
        result = learner.build_precedents_block("send-email", "hash", mode="active")
        assert result is not None
        assert "[PRECEDENTS]" in result
        assert "[/PRECEDENTS]" in result
        assert "send-email" in result
        assert "rejected" in result

    def test_block_contains_reason(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb(decision="approved", reason="safe read-only op"))
        result = learner.build_precedents_block("send-email", "hash", mode="active")
        assert result is not None
        assert "safe read-only op" in result


# ── TestGetBiasSummary ────────────────────────────────────────────────────────


class TestGetBiasSummary:
    def test_empty_store_returns_zero_rates(self) -> None:
        learner = FeedbackLearner()
        report = learner.get_bias_summary()
        assert report.rejection_rate == 0.0
        assert report.approval_rate == 1.0
        assert report.total_decisions == 0
        assert report.top_rejected_action_types == []

    def test_all_rejected(self) -> None:
        learner = FeedbackLearner()
        for _ in range(4):
            learner.record(_fb(decision="rejected"))
        report = learner.get_bias_summary()
        assert report.rejection_rate == 1.0
        assert report.approval_rate == 0.0
        assert report.total_decisions == 4

    def test_mixed_decisions(self) -> None:
        learner = FeedbackLearner()
        learner.record(_fb(decision="approved"))
        learner.record(_fb(decision="rejected"))
        report = learner.get_bias_summary()
        assert report.rejection_rate == pytest.approx(0.5)
        assert report.total_decisions == 2

    def test_top_rejected_action_types_ordered(self) -> None:
        learner = FeedbackLearner()
        for _ in range(3):
            learner.record(_fb(action_type="send-email", decision="rejected"))
        for _ in range(1):
            learner.record(_fb(action_type="delete-record", decision="rejected"))
        report = learner.get_bias_summary()
        assert report.top_rejected_action_types[0] == "send-email"

    def test_excludes_old_records_from_window(self) -> None:
        learner = FeedbackLearner()
        old_ts = datetime.now(UTC) - timedelta(days=31)
        learner._store.append((_fb(decision="rejected"), old_ts))
        report = learner.get_bias_summary()
        assert report.total_decisions == 0


# ── TestFeedbackFromHitlDecision ──────────────────────────────────────────────


class TestFeedbackFromHitlDecision:
    def test_builds_feedback_with_hash(self) -> None:
        fb = FeedbackLearner.feedback_from_hitl_decision(
            action_type="send-email",
            action_parameters={"to": "user@example.com"},
            decision="approved",
            rationale="low risk",
            agent_id="agent-1",
            request_id="req-123",
        )
        assert fb.action_type == "send-email"
        assert fb.decision == "approved"
        assert fb.decision_reason == "low risk"
        assert fb.agent_id == "agent-1"
        assert fb.action_id == "req-123"
        assert len(fb.payload_hash) == 64  # sha256 hex

    def test_same_params_produce_same_hash(self) -> None:
        params = {"key": "value", "num": 42}
        fb1 = FeedbackLearner.feedback_from_hitl_decision("a", params, "approved", "", "ag")
        fb2 = FeedbackLearner.feedback_from_hitl_decision("a", params, "rejected", "", "ag")
        assert fb1.payload_hash == fb2.payload_hash

    def test_different_params_produce_different_hash(self) -> None:
        fb1 = FeedbackLearner.feedback_from_hitl_decision("a", {"x": 1}, "approved", "", "ag")
        fb2 = FeedbackLearner.feedback_from_hitl_decision("a", {"x": 2}, "approved", "", "ag")
        assert fb1.payload_hash != fb2.payload_hash
