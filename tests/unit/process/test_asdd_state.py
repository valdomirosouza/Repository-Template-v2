"""Unit tests for scripts/asdd_state.py — delivery agent shared state (ADR-0058)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "asdd_state.py"


def _load():
    spec = importlib.util.spec_from_file_location("asdd_state", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def _handoff(**over):
    base = {
        "status": "done",
        "phase": 0,
        "agent": "asdd-phase-0-intake",
        "artifacts": ["intake-form.md"],
        "handoff_to": "asdd-phase-1-conception",
        "reason": "",
        "notes": "ok",
    }
    base.update(over)
    return base


def test_init_creates_state(mod, tmp_path):
    state = mod.init_state("FEAT-1", "Title", "normal feature", root=tmp_path)
    assert state["feature_id"] == "FEAT-1"
    assert state["current_phase"] == 0
    assert mod.state_path("FEAT-1", root=tmp_path).exists()


def test_load_missing_raises(mod, tmp_path):
    with pytest.raises(FileNotFoundError):
        mod.load_state("nope", root=tmp_path)


def test_append_handoff_updates_state(mod, tmp_path):
    mod.init_state("FEAT-2", "T", "normal feature", root=tmp_path)
    state = mod.append_handoff("FEAT-2", _handoff(phase=2, status="done"), root=tmp_path)
    assert state["current_phase"] == 2
    assert state["blocked"] is False
    assert len(state["handoffs"]) == 1
    assert "intake-form.md" in state["artifacts"]


def test_blocked_handoff_sets_blocked(mod, tmp_path):
    mod.init_state("FEAT-3", "T", "high-risk feature", root=tmp_path)
    state = mod.append_handoff(
        "FEAT-3", _handoff(status="blocked", reason="missing nfr.md"), root=tmp_path
    )
    assert state["blocked"] is True


def test_validate_rejects_bad_status(mod):
    assert any("status" in e for e in mod.validate_handoff(_handoff(status="weird")))


def test_validate_rejects_out_of_range_phase(mod):
    assert any("phase" in e for e in mod.validate_handoff(_handoff(phase=99)))


def test_validate_requires_reason_when_blocked(mod):
    errs = mod.validate_handoff(_handoff(status="blocked", reason=""))
    assert any("reason" in e for e in errs)


def test_append_invalid_handoff_raises(mod, tmp_path):
    mod.init_state("FEAT-4", "T", "normal feature", root=tmp_path)
    with pytest.raises(ValueError):
        mod.append_handoff("FEAT-4", _handoff(status="blocked", reason=""), root=tmp_path)


def test_human_gate_defaults_false_then_recorded(mod, tmp_path):
    mod.init_state("FEAT-5", "T", "normal feature", root=tmp_path)
    state = mod.append_handoff("FEAT-5", _handoff(phase=2, human_gate=True), root=tmp_path)
    assert state["handoffs"][-1]["human_gate"] is True


def test_cli_init_and_show(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert (
        mod.main(["init", "--feature", "FEAT-9", "--title", "X", "--risk-class", "small bug fix"])
        == 0
    )
    assert mod.main(["show", "--feature", "FEAT-9"]) == 0
    out = capsys.readouterr().out
    assert "FEAT-9" in out
