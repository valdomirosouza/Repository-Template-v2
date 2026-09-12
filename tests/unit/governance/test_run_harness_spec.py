"""Unit tests for scripts/governance/run_harness_spec.py (W12-T8, issue #361)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import run_harness_spec as rh  # noqa: E402

pytestmark = pytest.mark.unit


def _spec(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "spec.yml"
    p.write_text(body)
    return p


def test_blocking_failure_fails_and_non_blocking_only_warns(tmp_path: Path, capsys):
    spec = _spec(
        tmp_path,
        "gates:\n"
        "  - name: ok\n    command: 'true'\n    blocking: true\n"
        "  - name: soft\n    command: 'exit 3'\n    blocking: false\n"
        "  - name: hard\n    command: 'echo boom; exit 2'\n    blocking: true\n",
    )
    rc = rh.main([str(spec)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[PASS] ok" in out and "[WARN] soft" in out and "[FAIL] hard" in out
    assert "::error::harness gate `hard` failed (rc=2)" in out
    assert "::warning::harness gate `soft` failed (rc=3)" in out
    assert "RESULT: FAIL (1 blocking gate(s))" in out


def test_only_and_skip_select_gates(tmp_path: Path, capsys):
    spec = _spec(
        tmp_path,
        "gates:\n"
        "  - name: a\n    command: 'true'\n"
        "  - name: b\n    command: 'false'\n"
        "  - name: c\n    command: 'true'\n",
    )
    assert rh.main([str(spec), "--skip", "b"]) == 0
    assert rh.main([str(spec), "--only", "b"]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] b" in out


def test_dry_run_executes_nothing(tmp_path: Path, capsys):
    spec = _spec(tmp_path, "gates:\n  - name: x\n    command: 'exit 9'\n")
    assert rh.main([str(spec), "--dry-run"]) == 0
    assert "[dry-run] exit 9" in capsys.readouterr().out


def test_malformed_spec_returns_2(tmp_path: Path, capsys):
    spec = _spec(tmp_path, "steps:\n  - name: not-a-gate\n")
    assert rh.main([str(spec)]) == 2
    assert "::error::" in capsys.readouterr().out


def test_every_repo_harness_spec_with_gates_parses():
    """The four runnable specs load; business-value-check uses `steps:` and is descriptive."""
    for name in ("code-check", "doc-check", "release-check", "staging-check"):
        gates = rh.load_gates(REPO_ROOT / "harness" / f"{name}.yml")
        assert gates and all("command" in g for g in gates), name
