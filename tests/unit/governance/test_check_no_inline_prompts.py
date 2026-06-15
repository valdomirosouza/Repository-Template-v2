"""Unit tests for the no-inline-prompt governance gate (ADR-0079).

`check_no_inline_prompts` is the ratchet that keeps externalised agent system prompts from
drifting back into inline Python constants. As with the other governance gates, it is asserted
green against the real `src/agents/` tree (so the gate cannot silently start failing on main) and
red against crafted fixtures (so the gate cannot silently stop catching a reintroduced prompt).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_no_inline_prompts as cnip  # noqa: E402

pytestmark = pytest.mark.unit


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------- happy path (real repo)


def test_no_inline_prompts_on_real_repo():
    """The shipped src/agents/ tree must be clean — prompts live under prompts/ (ADR-0079)."""
    root = REPO_ROOT / "src" / "agents"
    assert cnip.scan(root) == []


def test_main_returns_zero_on_real_repo():
    assert cnip.main(["--root", str(REPO_ROOT / "src" / "agents")]) == 0


# --------------------------------------------------------------------- failure: reintroduced prompt


def test_flags_reintroduced_inline_system_prompt(tmp_path):
    """A reintroduced ``_SYSTEM_PROMPT = \"\"\"You are ...\"\"\"`` must fail the gate."""
    _write(
        tmp_path / "planner.py",
        '_SYSTEM_PROMPT = """\\\n'
        "You are a senior planning agent. Decompose the task into sprints.\n"
        "Output strict JSON only.\n"
        '"""\n',
    )
    findings = cnip.scan(tmp_path)
    assert len(findings) == 1
    assert findings[0].name == "_SYSTEM_PROMPT"
    assert "ADR-0079" in findings[0].reason


def test_main_returns_one_on_violation(tmp_path):
    _write(
        tmp_path / "evaluator.py",
        '_EVALUATOR_PROMPT = """You are an evaluator. You must score the output."""\n',
    )
    assert cnip.main(["--root", str(tmp_path)]) == 1


def test_flags_anonymous_long_marker_literal(tmp_path):
    """A long multi-line marker literal under an innocuous name is still caught."""
    body = "You are an autonomous agent.\n" + ("Follow every instruction precisely. " * 5)
    _write(tmp_path / "x.py", f'INSTRUCTIONS = """\\\n{body}\n"""\n')
    findings = cnip.scan(tmp_path)
    assert any(f.name == "INSTRUCTIONS" for f in findings)


# --------------------------------------------------------------------- exemptions (must NOT flag)


def test_does_not_flag_prompt_loader(tmp_path):
    """The loader is the sanctioned home for prompts and is exempt."""
    _write(
        tmp_path / "prompt_loader.py",
        '_SYSTEM_PROMPT = """You are a prompt. You must not be flagged here."""\n',
    )
    assert cnip.scan(tmp_path) == []


def test_does_not_flag_handoff_template(tmp_path):
    """A ``*_TEMPLATE`` handoff string (e.g. _RESTORE_TEMPLATE) is a distinct concept, not a prompt."""
    _write(
        tmp_path / "context_manager.py",
        '_RESTORE_TEMPLATE = """\\\n'
        "You are resuming a task. Here is the context summary from the previous session:\n"
        "{decisions}\n"
        '"""\n',
    )
    assert cnip.scan(tmp_path) == []


def test_does_not_flag_short_inline_fragment(tmp_path):
    """Short single-line instruction fragments at a call site are out of scope."""
    _write(
        tmp_path / "coordinator.py",
        'system = "You are an expert software engineer implementing a product sprint."\n',
    )
    assert cnip.scan(tmp_path) == []


def test_does_not_flag_truncation_marker(tmp_path):
    """A multi-line ``*_MARKER`` with no prompt phrasing is not a prompt."""
    _write(tmp_path / "sandbox_executor.py", '_TRUNCATION_MARKER = "\\n[OUTPUT TRUNCATED]"\n')
    assert cnip.scan(tmp_path) == []


def test_respects_inline_waiver(tmp_path):
    """An ``# inline-prompt-ok:`` waiver on the assignment line suppresses the finding."""
    _write(
        tmp_path / "special.py",
        '_SYSTEM_PROMPT = """You are special."""  # inline-prompt-ok: bootstrap literal, see ADR-XXXX\n',
    )
    assert cnip.scan(tmp_path) == []
