"""Tests for tools.yaml catalog loading + startup reversibility validation.

ADR-0055 — the canonical tools.yaml must declare reversibility metadata for every
tool; missing fields fail startup in production (strict mode).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agents.tool_registry import (
    REVERSIBILITY_FIELDS,
    ToolCatalogError,
    load_tools_from_yaml,
)

_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_YAML = _ROOT / "infrastructure" / "agent-tools" / "tools.yaml"


def test_real_catalog_loads_strict():
    """The committed tools.yaml must pass strict (production) validation."""
    registry = load_tools_from_yaml(_TOOLS_YAML, strict=True)
    assert len(registry.all()) >= 7


def test_every_catalog_tool_declares_reversibility_metadata():
    raw = yaml.safe_load(_TOOLS_YAML.read_text())
    for entry in raw["tools"]:
        missing = [f for f in REVERSIBILITY_FIELDS if f not in entry]
        assert not missing, f"tool '{entry.get('name')}' missing {missing}"


def test_reversibility_metadata_round_trips():
    registry = load_tools_from_yaml(_TOOLS_YAML, strict=True)
    assert registry.is_reversible("read-db-record") is True
    assert registry.is_reversible("send-email") is False
    assert registry.compensating_action("write-db-record") == "restore-db-record"
    assert registry.max_hotl_risk_score("read-db-record") == pytest.approx(0.3)
    assert registry.requires_dual_approval("execute-code") is True


def test_strict_mode_rejects_missing_reversibility_fields(tmp_path):
    catalog = {
        "tools": [
            {
                "name": "bad-tool",
                "description": "missing reversibility metadata",
                "version": "1.0",
                "risk_level": "low",
                "pii_access": [],
                "requires_hitl": False,
                "execution_mode": "direct",
                "rate_limit_per_minute": 10,
                "rate_limit_per_hour": 100,
                "owner_team": "platform",
                # no reversible / compensating_action / max_hotl_risk_score / allowed_autonomy_levels
            }
        ]
    }
    path = tmp_path / "tools.yaml"
    path.write_text(yaml.safe_dump(catalog))

    with pytest.raises(ToolCatalogError, match="reversibility"):
        load_tools_from_yaml(path, strict=True)


def test_non_strict_mode_allows_missing_fields_with_defaults(tmp_path):
    catalog = {
        "tools": [
            {
                "name": "lenient-tool",
                "description": "no reversibility metadata",
                "version": "1.0",
                "risk_level": "low",
                "pii_access": [],
                "requires_hitl": False,
                "execution_mode": "direct",
                "rate_limit_per_minute": 10,
                "rate_limit_per_hour": 100,
                "owner_team": "platform",
            }
        ]
    }
    path = tmp_path / "tools.yaml"
    path.write_text(yaml.safe_dump(catalog))

    registry = load_tools_from_yaml(path, strict=False)
    # Conservative defaults: non-reversible, never auto-HOTL.
    assert registry.is_reversible("lenient-tool") is False
    assert registry.max_hotl_risk_score("lenient-tool") == 0.0


def test_malformed_catalog_raises(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text("not: a tools list")
    with pytest.raises(ToolCatalogError, match="tools"):
        load_tools_from_yaml(path, strict=False)
