"""Unit tests for src/shared/feature_flags.py.

Uses OpenFeature InMemoryProvider — no flagd service required.

Spec: SPEC-autonomous-mode-levels, specs/system/architecture.md
ADR:  ADR-0015 (Feature Flag Strategy — revised)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openfeature import api
from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

from src.shared.feature_flags import (
    AutonomyLevel,
    _parse_action_types,
    get_autonomy_level,
    is_autonomous_mode_enabled,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_bool_flag(enabled: bool) -> InMemoryFlag:
    variant = "on" if enabled else "off"
    return InMemoryFlag(default_variant=variant, variants={"on": True, "off": False})


def _set_provider(**flags: bool) -> None:
    """Configure InMemoryProvider with the given flag name → bool mapping."""
    in_memory_flags = {name: _make_bool_flag(val) for name, val in flags.items()}
    api.set_provider(InMemoryProvider(in_memory_flags))


def _all_off() -> None:
    """Set all autonomy flags to disabled."""
    _set_provider(
        **{
            "autonomous-mode": False,
            "autonomous-mode-full": False,
            "autonomous-mode-medium-risk": False,
            "autonomous-mode-low-risk": False,
            "autonomous-mode-tests-only": False,
            "autonomous-mode-read-only": False,
        }
    )


# ── is_autonomous_mode_enabled (legacy, unchanged) ────────────────────────────


class TestIsAutonomousModeEnabled:
    def test_returns_false_when_flag_is_off(self):
        _set_provider(**{"autonomous-mode": False})
        assert is_autonomous_mode_enabled() is False

    def test_returns_true_when_flag_is_on(self):
        _set_provider(**{"autonomous-mode": True})
        assert is_autonomous_mode_enabled() is True

    def test_flag_off_overrides_settings_true_default(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", True)
        _set_provider(**{"autonomous-mode": False})
        assert is_autonomous_mode_enabled() is False

    def test_flag_on_overrides_settings_false_default(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", False)
        _set_provider(**{"autonomous-mode": True})
        assert is_autonomous_mode_enabled() is True

    def test_falls_back_to_settings_when_sdk_raises(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", True)
        mock_client = MagicMock()
        mock_client.get_boolean_value.side_effect = RuntimeError("provider unavailable")
        with patch("openfeature.api.get_client", return_value=mock_client):
            result = is_autonomous_mode_enabled()
        assert result is True

    def test_falls_back_to_settings_false_on_sdk_error(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", False)
        mock_client = MagicMock()
        mock_client.get_boolean_value.side_effect = RuntimeError("provider unavailable")
        with patch("openfeature.api.get_client", return_value=mock_client):
            result = is_autonomous_mode_enabled()
        assert result is False


# ── get_autonomy_level — NONE (all off) ───────────────────────────────────────


class TestGetAutonomyLevelNone:
    def test_returns_none_when_all_flags_off(self):
        _all_off()
        assert get_autonomy_level("deploy", 0.5) == AutonomyLevel.NONE

    def test_returns_none_when_sdk_raises(self):
        with patch("openfeature.api.get_client", side_effect=RuntimeError("down")):
            assert get_autonomy_level("deploy", 0.1) == AutonomyLevel.NONE

    def test_returns_none_for_high_risk_even_if_low_risk_enabled(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_low_risk_threshold", 0.3)
        _set_provider(**{"autonomous-mode-low-risk": True})
        # risk_score 0.5 ≥ 0.3 → LOW_RISK does not apply
        assert get_autonomy_level("deploy", 0.5) == AutonomyLevel.NONE


# ── get_autonomy_level — READ_ONLY ────────────────────────────────────────────


class TestGetAutonomyLevelReadOnly:
    def test_returns_read_only_for_read_action(self, monkeypatch):
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_read_only_action_types",
            "read_file,search_code,list_files,get_status,read_spec,read_adr",
        )
        _set_provider(**{"autonomous-mode-read-only": True})
        assert get_autonomy_level("read_file", 0.9) == AutonomyLevel.READ_ONLY

    def test_does_not_apply_to_non_read_action(self, monkeypatch):
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_read_only_action_types",
            "read_file,search_code",
        )
        _all_off()
        _set_provider(**{"autonomous-mode-read-only": True})
        assert get_autonomy_level("deploy", 0.1) == AutonomyLevel.NONE

    def test_any_risk_score_allowed_for_read_only(self, monkeypatch):
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_read_only_action_types", "read_file"
        )
        _set_provider(**{"autonomous-mode-read-only": True})
        assert get_autonomy_level("read_file", 0.99) == AutonomyLevel.READ_ONLY


# ── get_autonomy_level — TESTS_ONLY ──────────────────────────────────────────


class TestGetAutonomyLevelTestsOnly:
    def test_returns_tests_only_for_test_action(self, monkeypatch):
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_test_action_types",
            "generate_test,run_test,check_coverage,lint_check",
        )
        _set_provider(**{"autonomous-mode-tests-only": True})
        assert get_autonomy_level("run_test", 0.8) == AutonomyLevel.TESTS_ONLY

    def test_does_not_apply_to_non_test_action(self, monkeypatch):
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_test_action_types", "generate_test"
        )
        _set_provider(**{"autonomous-mode-tests-only": True})
        assert get_autonomy_level("deploy", 0.1) == AutonomyLevel.NONE

    def test_tests_only_takes_priority_over_read_only(self, monkeypatch):
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_test_action_types", "run_test"
        )
        monkeypatch.setattr(
            "src.shared.feature_flags.settings.autonomy_read_only_action_types", "run_test"
        )
        _set_provider(**{"autonomous-mode-tests-only": True, "autonomous-mode-read-only": True})
        # TESTS_ONLY is evaluated before READ_ONLY
        assert get_autonomy_level("run_test", 0.5) == AutonomyLevel.TESTS_ONLY


# ── get_autonomy_level — LOW_RISK ─────────────────────────────────────────────


class TestGetAutonomyLevelLowRisk:
    def test_returns_low_risk_below_threshold(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_low_risk_threshold", 0.3)
        _set_provider(**{"autonomous-mode-low-risk": True})
        assert get_autonomy_level("deploy", 0.2) == AutonomyLevel.LOW_RISK

    def test_boundary_exactly_at_threshold_excluded(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_low_risk_threshold", 0.3)
        _set_provider(**{"autonomous-mode-low-risk": True})
        # risk_score == 0.3 is NOT < 0.3
        assert get_autonomy_level("deploy", 0.3) == AutonomyLevel.NONE

    def test_low_risk_applies_to_any_action_type(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_low_risk_threshold", 0.3)
        _set_provider(**{"autonomous-mode-low-risk": True})
        assert get_autonomy_level("deploy", 0.29) == AutonomyLevel.LOW_RISK
        assert get_autonomy_level("read_file", 0.1) == AutonomyLevel.LOW_RISK


# ── get_autonomy_level — MEDIUM_RISK ─────────────────────────────────────────


class TestGetAutonomyLevelMediumRisk:
    def test_returns_medium_risk_at_or_below_threshold(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_medium_risk_threshold", 0.7)
        _set_provider(**{"autonomous-mode-medium-risk": True})
        assert get_autonomy_level("deploy", 0.7) == AutonomyLevel.MEDIUM_RISK

    def test_does_not_apply_above_threshold(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_medium_risk_threshold", 0.7)
        _set_provider(**{"autonomous-mode-medium-risk": True})
        assert get_autonomy_level("deploy", 0.71) == AutonomyLevel.NONE

    def test_medium_risk_takes_priority_over_low_risk(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_low_risk_threshold", 0.3)
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_medium_risk_threshold", 0.7)
        _set_provider(**{"autonomous-mode-medium-risk": True, "autonomous-mode-low-risk": True})
        # risk_score 0.2 qualifies for BOTH medium-risk and low-risk;
        # MEDIUM_RISK is evaluated first → wins
        assert get_autonomy_level("deploy", 0.2) == AutonomyLevel.MEDIUM_RISK


# ── get_autonomy_level — FULL ─────────────────────────────────────────────────


class TestGetAutonomyLevelFull:
    def test_returns_full_when_flag_enabled(self):
        _set_provider(**{"autonomous-mode-full": True})
        assert get_autonomy_level("deploy", 0.99) == AutonomyLevel.FULL

    def test_full_takes_priority_over_all_other_levels(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_low_risk_threshold", 0.3)
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomy_medium_risk_threshold", 0.7)
        _set_provider(
            **{
                "autonomous-mode-full": True,
                "autonomous-mode-medium-risk": True,
                "autonomous-mode-low-risk": True,
                "autonomous-mode-tests-only": True,
                "autonomous-mode-read-only": True,
            }
        )
        assert get_autonomy_level("read_file", 0.0) == AutonomyLevel.FULL

    def test_returns_none_when_full_disabled_and_all_others_off(self):
        _all_off()
        assert get_autonomy_level("deploy", 0.5) == AutonomyLevel.NONE


# ── _parse_action_types ───────────────────────────────────────────────────────


class TestParseActionTypes:
    def test_parses_comma_separated(self):
        result = _parse_action_types("read_file,search_code,list_files")
        assert result == frozenset({"read_file", "search_code", "list_files"})

    def test_strips_whitespace(self):
        result = _parse_action_types("read_file , search_code , list_files")
        assert "read_file" in result
        assert "search_code" in result

    def test_empty_string_returns_empty(self):
        assert _parse_action_types("") == frozenset()

    def test_single_entry(self):
        assert _parse_action_types("deploy") == frozenset({"deploy"})
