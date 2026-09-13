"""Configuration validation tests (scaffold starter, W15-T5).

A service must start from its documented defaults and honour environment overrides — the two
things that break first when a template is copied.
"""

from __future__ import annotations

import pytest

from __MODULE_NAME__.config import Settings


def test_defaults_are_the_documented_ones() -> None:
    s = Settings(_env_file=None)  # ignore any local .env
    assert s.app_env == "development"
    assert s.app_port == 8000
    assert s.log_level == "INFO"
    assert s.service_name == "__SERVICE_NAME__"
    assert s.otel_exporter_otlp_endpoint.startswith("http://")


def test_environment_overrides_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "9001")
    monkeypatch.setenv("APP_ENV", "staging")
    s = Settings(_env_file=None)
    assert s.app_port == 9001 and s.app_env == "staging"


def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "not-a-port")
    with pytest.raises(Exception):
        Settings(_env_file=None)
