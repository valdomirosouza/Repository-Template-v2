#!/usr/bin/env python3
"""Fail if a new inline agent system-prompt string reappears in ``src/agents/`` (ADR-0079).

ADR-0079 externalised the harness/orchestrator system prompts out of inline Python constants
into versioned files under ``prompts/``, loaded byte-for-byte by ``src/agents/prompt_loader.py``.
Once externalised, a prompt that drifts back into a Python constant escapes the prompt registry,
loses its version pin, and silently diverges from the on-disk source of truth. This gate is the
ratchet that keeps that from happening: it scans ``src/agents/`` for string literals that look
like an LLM system prompt and fails when one reappears outside the loader.

Heuristic (AST-based, robust against formatting):
  A string Constant is flagged when it is a *prompt-shaped* literal, i.e. it is

    - assigned to a name containing ``PROMPT`` (the externalised pattern was
      ``_SYSTEM_PROMPT = \"\"\"You are ...\"\"\"``), and is either multi-line or carries a
      system-prompt marker; OR
    - a long (>= ``_MIN_ANON_LEN`` char), multi-line literal that carries a system-prompt
      marker ("You are" / "You must" / "Your task is" / "You should") — this catches a prompt
      reintroduced under an innocuous name or as a bare expression.

  Deliberately *not* flagged:
    - ``src/agents/prompt_loader.py`` — it is the sanctioned home for loading prompts.
    - Names ending in ``_TEMPLATE`` / ``_MARKER`` — handoff templates and output markers are a
      distinct concept from a model system prompt (e.g. ``_RESTORE_TEMPLATE``).
    - Short inline instruction fragments (single-line f-strings passed at a call site) — these
      are not the large externalised constants ADR-0079 governs.
    - Anything in the explicit ``_ALLOWLIST`` (justified) or carrying a
      ``# inline-prompt-ok: <reason>`` waiver comment on the assignment's line.

Usage:
    python3 scripts/governance/check_no_inline_prompts.py            # scan src/agents
    python3 scripts/governance/check_no_inline_prompts.py --root src/agents

Exit 0 = clean; exit 1 = a new inline system-prompt constant (use as a CI gate).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ROOT = "src/agents"

# Phrases that strongly signal an LLM *system prompt* (role / instruction framing).
_PROMPT_MARKERS = ("You are", "You must", "Your task is", "You should")

# A name containing this token is the externalised pattern (``_SYSTEM_PROMPT``, ``PLANNER_PROMPT``).
_PROMPT_NAME_TOKEN = "PROMPT"

# Name suffixes that denote a different concept (handoff template, output marker), not a prompt.
_NON_PROMPT_SUFFIXES = ("_TEMPLATE", "_MARKER")

# An anonymous (non ``*PROMPT*``-named) literal must be at least this long, multi-line, and carry
# a marker before it is flagged — keeps short inline instruction fragments out of scope.
_MIN_ANON_LEN = 120

# Files exempt from the gate (relative to the scan root). The loader is the sanctioned home.
_EXEMPT_FILES = {"prompt_loader.py"}

# Explicit, justified allow-list of (relative_path, constant_name) pairs. Empty by design — add an
# entry here (with a justification comment) only when a prompt-shaped constant is genuinely required
# inline and externalisation is not appropriate. Prefer the on-disk prompts/ registry (ADR-0079).
_ALLOWLIST: set[tuple[str, str]] = set()

# Inline escape hatch: ``# inline-prompt-ok: <reason>`` on the line of the assignment.
_WAIVER_MARKER = "inline-prompt-ok:"


class _Finding:
    __slots__ = ("line", "name", "path", "reason")

    def __init__(self, path: str, line: int, name: str, reason: str) -> None:
        self.path = path
        self.line = line
        self.name = name
        self.reason = reason

    def render(self) -> str:
        who = self.name or "<anonymous literal>"
        return f"  - {self.path}:{self.line}: {who} — {self.reason}"


def _has_marker(text: str) -> bool:
    return any(marker in text for marker in _PROMPT_MARKERS)


def _waived(lines: list[str], lineno: int) -> bool:
    """True if the assignment line (1-indexed) carries an ``# inline-prompt-ok:`` waiver."""
    if 1 <= lineno <= len(lines):
        return _WAIVER_MARKER in lines[lineno - 1]
    return False


def _names_for(node: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(node, ast.AnnAssign):
        targets: list[ast.expr] = [node.target]
    else:
        targets = list(node.targets)
    return [t.id for t in targets if isinstance(t, ast.Name)]


_REASON_PROMPT_NAME = (
    "inline system prompt assigned to a *PROMPT* constant "
    "(externalise via prompt_loader, ADR-0079)"
)
_REASON_LONG_LITERAL = (
    "long multi-line literal with system-prompt phrasing "
    "(externalise via prompt_loader, ADR-0079)"
)


def _classify(name: str, value: str) -> str | None:
    """Return a violation reason if ``name = value`` is prompt-shaped, else ``None``.

    ``name`` is ``""`` for a bare string-expression statement.
    """
    upper = name.upper()
    if any(upper.endswith(suffix) for suffix in _NON_PROMPT_SUFFIXES):
        return None

    multiline = "\n" in value
    marker = _has_marker(value)

    # Strongest signal: a *PROMPT*-named constant that is multi-line or carries a marker.
    if _PROMPT_NAME_TOKEN in upper and (multiline or marker):
        return _REASON_PROMPT_NAME

    # Anonymous or innocuously-named: only a long multi-line marker literal counts.
    if multiline and marker and len(value) >= _MIN_ANON_LEN:
        return _REASON_LONG_LITERAL

    return None


def _scan_file(path: Path, rel: str) -> list[_Finding]:
    findings: list[_Finding] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        # A non-parseable file can't define a constant we govern; let other gates flag it.
        return findings

    for node in ast.walk(tree):
        # Named assignments: ``X = "..."`` and ``X: T = "..."``.
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            for name in _names_for(node):
                if (rel, name) in _ALLOWLIST:
                    continue
                if _waived(lines, node.lineno):
                    continue
                reason = _classify(name, value.value)
                if reason is not None:
                    findings.append(_Finding(rel, value.lineno, name, reason))
        # Bare string expression statements: a prompt left as a loose docstring-style literal.
        elif isinstance(node, ast.Expr):
            value = node.value
            if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            if _waived(lines, node.lineno):
                continue
            reason = _classify("", value.value)
            if reason is not None:
                findings.append(_Finding(rel, value.lineno, "", reason))

    return findings


def scan(root: Path) -> list[_Finding]:
    findings: list[_Finding] = []
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        if rel in _EXEMPT_FILES:
            continue
        findings.extend(_scan_file(path, rel))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(_REPO_ROOT / _DEFAULT_ROOT))
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 1

    findings = scan(root)
    if findings:
        print(
            "New inline agent system prompt(s) found in src/agents/ (ADR-0079):",
            file=sys.stderr,
        )
        for f in findings:
            print(f.render(), file=sys.stderr)
        print(
            "\nMove the prompt to a versioned file under prompts/ and load it via "
            "src/agents/prompt_loader.load_prompt(), per ADR-0079. If a prompt-shaped "
            "constant is genuinely required inline, add an '# inline-prompt-ok: <reason>' "
            "waiver or an entry in _ALLOWLIST (with justification).",
            file=sys.stderr,
        )
        return 1
    print("OK — no inline agent system prompts in src/agents/ (ADR-0079).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
