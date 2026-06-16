#!/usr/bin/env python3
"""Governance gate: no NEW inline LLM system prompts in ``src/agents/`` (ADR-0079).

System prompts are versioned configuration that changes model behaviour, so they
belong in ``prompts/<area>/<name>.vN.md`` (loaded via ``src/agents/prompts``), not
as inline Python string literals. This gate fails when a system-prompt-shaped
string literal appears in ``src/agents/**/*.py`` **outside the allow-list**.

The allow-list pins the prompts that ADR-0079 phases (it does *not* migrate them
in one shot — see the ADR's phased plan). It deliberately does **not** include the
two prompts this ADR externalised (``harness.evaluator``, ``orchestrator.reason``):
if either reappears inline, the gate fails — that is the regression it guards.

Exit codes: 0 = clean, 1 = a disallowed inline prompt was found (with ``::error::``).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_DIR = _REPO_ROOT / "src" / "agents"

# A system-prompt-shaped literal: "You are <role> ... (engineer|agent|writer|reviewer|planner)".
_PROMPT_RE = re.compile(r"You are .{0,40}(engineer|agent|writer|reviewer|planner)")

# Allow-list of substrings of prompts NOT migrated by ADR-0079 (phased migration).
# A match is permitted iff one of these substrings appears in the matched literal.
# The two externalised prompts are intentionally ABSENT so they cannot reappear inline.
_ALLOWED_FRAGMENTS: tuple[str, ...] = (
    # harness.planner — src/agents/harness/planner.py
    "You are a product planning agent",
    # subagent.<role> — src/agents/harness/sub_agent_registry.py
    "You are a security reviewer",
    "You are a technical writer",
    # harness.coordinator — src/agents/harness/coordinator.py
    "You are an expert software engineer implementing a product sprint",
    "You are a senior engineer performing structured self-reflection",
    # context_manager restore template (src/agents/harness/context_manager.py)
    "You are resuming",
)


def _iter_agent_py_files() -> list[Path]:
    return sorted(p for p in _AGENTS_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def main() -> int:
    violations: list[tuple[Path, int, str]] = []

    for path in _iter_agent_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover — unreadable file is itself a failure
            print(f"::error file={path}::could not read file: {exc}")
            return 1

        for lineno, line in enumerate(text.splitlines(), start=1):
            match = _PROMPT_RE.search(line)
            if match is None:
                continue
            fragment = match.group(0)
            if any(allowed in line for allowed in _ALLOWED_FRAGMENTS):
                continue
            violations.append((path, lineno, fragment))

    if violations:
        for path, lineno, fragment in violations:
            rel = path.relative_to(_REPO_ROOT)
            print(
                f"::error file={rel},line={lineno}::Inline LLM system prompt detected "
                f"({fragment!r}). Externalise it to prompts/<area>/<name>.vN.md and load "
                f"via src/agents/prompts (ADR-0079), or add it to the allow-list if it is a "
                f"phased-migration exception."
            )
        print(
            f"\ncheck_inline_prompts: FAIL — {len(violations)} disallowed inline prompt(s).",
            file=sys.stderr,
        )
        return 1

    print("check_inline_prompts: OK — no new inline LLM system prompts in src/agents/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
