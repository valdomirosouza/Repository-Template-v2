"""Unit tests for scripts/generate_context_graph.py (ADR-0057).

The context graph is a compact, deterministic repo map for agent bootstrap.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "generate_context_graph.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_context_graph", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture(scope="module")
def graph(mod):
    return mod.build_context_graph(_ROOT)


def test_schema_and_version(graph):
    assert graph["schema_version"] == "context_graph_v1"
    assert graph["version"] == (_ROOT / "version.txt").read_text().strip()


def test_top_level_sections_present(graph):
    for key in ("specs", "adrs", "skills", "services", "tools", "features", "checksums"):
        assert key in graph, f"context graph missing section '{key}'"


def test_adrs_have_id_title_and_affects(graph):
    assert graph["adrs"], "expected at least one ADR"
    adr = graph["adrs"][0]
    assert adr["id"].startswith("ADR-")
    assert adr["title"]
    assert "affects" in adr


def test_specs_map_to_implementation(graph):
    # hitl-hotl spec is referenced by orchestrator/hotl modules via `Spec:` lines.
    hitl = next((s for s in graph["specs"] if s["path"].endswith("hitl-hotl.md")), None)
    assert hitl is not None
    assert any("orchestrator" in f or "hotl" in f for f in hitl["implemented_by"])


def test_tools_carry_risk_policy(graph):
    names = {t["name"] for t in graph["tools"]}
    assert "read-db-record" in names
    send_email = next(t for t in graph["tools"] if t["name"] == "send-email")
    assert send_email["requires_hitl"] is True
    assert send_email["reversible"] is False


def test_checksums_cover_key_files(graph):
    assert "version.txt" in graph["checksums"]
    assert "infrastructure/agent-tools/tools.yaml" in graph["checksums"]
    assert graph["checksums"]["version.txt"].startswith("sha256:")


def test_graph_is_under_size_budget(mod):
    payload = json.dumps(mod.build_context_graph(_ROOT), indent=2, sort_keys=True)
    size_kb = len(payload.encode()) / 1024
    assert size_kb < 50, f"context graph is {size_kb:.1f} KB (> 50 KB bootstrap budget)"


def test_build_is_deterministic_excluding_timestamp(mod):
    a = mod.build_context_graph(_ROOT, include_timestamp=False)
    b = mod.build_context_graph(_ROOT, include_timestamp=False)
    assert a == b
    assert "generated_at" not in a


def test_check_mode_detects_missing_file(mod, tmp_path):
    missing = tmp_path / "context-graph.json"
    assert mod.main(["--check", "--output", str(missing)]) == 1
