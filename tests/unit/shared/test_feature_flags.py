"""Unit tests for src/shared/feature_flags.py.

Uses OpenFeature InMemoryProvider — no flagd service required.

Spec: specs/system/architecture.md
ADR:  ADR-0015 (Feature Flag Strategy)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openfeature import api
from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

from src.shared.feature_flags import is_autonomous_mode_enabled


def _set_flag(enabled: bool) -> None:
    variant = "on" if enabled else "off"
    flag = InMemoryFlag(
        default_variant=variant,
        variants={"on": True, "off": False},
    )
    api.set_provider(InMemoryProvider({"autonomous-mode": flag}))


class TestIsAutonomousModeEnabled:
    def test_returns_false_when_flag_is_off(self):
        _set_flag(False)
        assert is_autonomous_mode_enabled() is False

    def test_returns_true_when_flag_is_on(self):
        _set_flag(True)
        assert is_autonomous_mode_enabled() is True

    def test_flag_off_overrides_settings_true_default(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", True)
        _set_flag(False)
        assert is_autonomous_mode_enabled() is False

    def test_flag_on_overrides_settings_false_default(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", False)
        _set_flag(True)
        assert is_autonomous_mode_enabled() is True

    def test_falls_back_to_settings_when_sdk_raises(self, monkeypatch):
        monkeypatch.setattr("src.shared.feature_flags.settings.autonomous_mode_enabled", True)
        # Simulate SDK client raising during evaluation
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
