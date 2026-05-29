"""Unit tests for RiskScorer — 5-factor weighted risk evaluation.

Spec: specs/ai/hitl-hotl.md (Risk Scoring Inputs)
"""

from __future__ import annotations

import pytest

from src.agents.risk_scorer import (
    RiskComponents,
    RiskScorer,
    _score_external,
    _score_irreversibility,
    _score_scale,
    _score_sensitivity,
)

# ── Factor: irreversibility ───────────────────────────────────────────────────


class TestIrreversibility:
    def test_delete_scores_maximum(self) -> None:
        assert _score_irreversibility("delete_user_records") == 1.0

    def test_drop_scores_maximum(self) -> None:
        assert _score_irreversibility("drop_table") == 1.0

    def test_truncate_scores_maximum(self) -> None:
        assert _score_irreversibility("truncate_logs") == 1.0

    def test_write_scores_high(self) -> None:
        assert _score_irreversibility("write_config") == 0.7

    def test_update_scores_high(self) -> None:
        assert _score_irreversibility("update_account") == 0.7

    def test_deploy_scores_high(self) -> None:
        assert _score_irreversibility("deploy_service") == 0.7

    def test_read_scores_low(self) -> None:
        assert _score_irreversibility("read_file") == 0.1

    def test_query_scores_low(self) -> None:
        assert _score_irreversibility("query_logs") == 0.1

    def test_unknown_scores_medium(self) -> None:
        # "process_data" contains no read/write keyword substrings → default 0.5
        assert _score_irreversibility("process_data") == 0.5


# ── Factor: external effect ───────────────────────────────────────────────────


class TestExternalEffect:
    def test_email_action_scores_maximum(self) -> None:
        assert _score_external("send_email", {}) == 1.0

    def test_webhook_action_scores_maximum(self) -> None:
        assert _score_external("trigger_webhook", {}) == 1.0

    def test_external_param_true_scores_maximum(self) -> None:
        assert _score_external("write_data", {"external": True}) == 1.0

    def test_production_env_scores_high(self) -> None:
        assert _score_external("deploy", {"target_env": "production"}) == 0.8

    def test_prod_env_scores_high(self) -> None:
        assert _score_external("deploy", {"target_env": "prod"}) == 0.8

    def test_internal_action_scores_low(self) -> None:
        assert _score_external("read_cache", {}) == 0.2

    def test_external_param_false_scores_low(self) -> None:
        assert _score_external("write_db", {"external": False}) == 0.2


# ── Factor: scale ─────────────────────────────────────────────────────────────


class TestScale:
    def test_count_1000_scores_maximum(self) -> None:
        assert _score_scale({"count": 1000}) == 1.0

    def test_count_over_1000_scores_maximum(self) -> None:
        assert _score_scale({"count": 5000}) == 1.0

    def test_count_100_scores_high(self) -> None:
        assert _score_scale({"count": 100}) == 0.7

    def test_count_10_scores_medium(self) -> None:
        assert _score_scale({"count": 10}) == 0.4

    def test_count_1_scores_low(self) -> None:
        assert _score_scale({"count": 1}) == 0.1

    def test_bulk_flag_scores_high(self) -> None:
        assert _score_scale({"bulk": True}) == 0.8

    def test_all_flag_scores_high(self) -> None:
        assert _score_scale({"all": True}) == 0.8

    def test_no_indicators_scores_low(self) -> None:
        assert _score_scale({"name": "test"}) == 0.1

    def test_entity_count_key_used(self) -> None:
        assert _score_scale({"entity_count": 200}) == 0.7

    def test_batch_size_key_used(self) -> None:
        assert _score_scale({"batch_size": 50}) == 0.4


# ── Factor: data sensitivity ──────────────────────────────────────────────────


class TestDataSensitivity:
    def test_l1_cpf_token_scores_maximum(self) -> None:
        assert _score_sensitivity({"user_id": "[CPF]"}) == 1.0

    def test_l1_health_token_scores_maximum(self) -> None:
        assert _score_sensitivity({"record": "[HEALTH]"}) == 1.0

    def test_l2_email_token_scores_medium(self) -> None:
        assert _score_sensitivity({"contact": "[EMAIL]"}) == 0.6

    def test_l2_phone_token_scores_medium(self) -> None:
        assert _score_sensitivity({"phone": "[PHONE]"}) == 0.6

    def test_l3_token_scores_low(self) -> None:
        assert _score_sensitivity({"session": "[TOKEN]"}) == 0.3

    def test_no_pii_scores_zero(self) -> None:
        assert _score_sensitivity({"action": "summarise", "text": "hello world"}) == 0.0

    def test_l1_takes_precedence_over_l2(self) -> None:
        params = {"a": "[SSN]", "b": "[EMAIL]"}
        assert _score_sensitivity(params) == 1.0


# ── Full scorer ───────────────────────────────────────────────────────────────


class TestRiskScorer:
    def test_returns_tuple_of_float_and_components(self) -> None:
        scorer = RiskScorer()
        score, components = scorer.score("read_file", {})
        assert isinstance(score, float)
        assert isinstance(components, RiskComponents)

    def test_score_clamped_to_zero_one(self) -> None:
        scorer = RiskScorer()
        score, _ = scorer.score("read_file", {})
        assert 0.0 <= score <= 1.0

    def test_low_risk_read_action(self) -> None:
        scorer = RiskScorer()
        score, _ = scorer.score("read_file", {"name": "config.yaml"})
        assert score < 0.4, f"Expected LOW risk, got {score}"

    def test_high_risk_delete_with_bulk_external(self) -> None:
        scorer = RiskScorer()
        score, _ = scorer.score(
            "delete_users",
            {"count": 5000, "external": True, "env": "[EMAIL]"},
        )
        assert score >= 0.7, f"Expected HIGH risk, got {score}"

    def test_medium_risk_write_internal(self) -> None:
        scorer = RiskScorer()
        score, _ = scorer.score("write_config", {"count": 1})
        assert 0.2 <= score <= 0.6, f"Expected MEDIUM risk, got {score}"

    def test_bias_provider_adds_rejection_rate(self) -> None:
        class _FakeBias:
            def get_bias(self, action_type: str) -> float:
                return 0.3  # simulates high historical rejection

        scorer = RiskScorer(bias_provider=_FakeBias())
        score_with_bias, _ = scorer.score("read_file", {})
        scorer_no_bias = RiskScorer()
        score_without, _ = scorer_no_bias.score("read_file", {})
        # Bias adds 0.05 * 0.3 = 0.015 — score should be higher with bias
        assert score_with_bias > score_without

    def test_bias_clamped_to_one(self) -> None:
        class _MaxBias:
            def get_bias(self, action_type: str) -> float:
                return 999.0  # out-of-range bias

        scorer = RiskScorer(bias_provider=_MaxBias())
        score, _ = scorer.score("delete_all", {"count": 9999, "external": True})
        assert score <= 1.0

    def test_components_weighted_total_matches_score(self) -> None:
        scorer = RiskScorer()
        score, components = scorer.score("send_email", {"count": 100})
        assert abs(score - components.weighted_total) < 1e-9

    def test_unknown_action_defaults_to_medium(self) -> None:
        scorer = RiskScorer()
        _, components = scorer.score("process_data", {})
        assert components.irreversibility == 0.5

    @pytest.mark.parametrize(
        "action_type,params,expected_tier",
        [
            ("read_file", {}, "LOW"),
            ("query_logs", {"count": 1}, "LOW"),
            # update_account + count=1 + no external → 0.245+0.05+0.02 = 0.315 (LOW)
            ("update_account", {"count": 1}, "LOW"),
            # update + bulk + external PII → clearly MEDIUM/HIGH
            ("update_account", {"count": 100, "external": True}, "MEDIUM"),
            ("delete_records", {"count": 1000, "external": True}, "HIGH"),
        ],
    )
    def test_risk_tier_parametrized(
        self, action_type: str, params: dict, expected_tier: str
    ) -> None:
        scorer = RiskScorer()
        score, _ = scorer.score(action_type, params)
        tier = "LOW" if score < 0.4 else ("MEDIUM" if score < 0.7 else "HIGH")
        assert tier == expected_tier, f"{action_type}: score={score:.3f}, expected {expected_tier}"
