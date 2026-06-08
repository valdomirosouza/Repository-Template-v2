#!/usr/bin/env python3
"""PreToolUse guard for high-risk, outward-facing / irreversible actions.

Closes F7 (docs/sdlc/deliver-dryrun-findings.md, issue #133): the `/deliver`
skill and its `phase-executor` subagent grant an unscoped `Bash` tool, so the
"never autonomously push / merge / release / deploy / change a flag" guarantees
were enforced **only by prose**. This hook moves them to the harness layer.

Decision policy (PreToolUse `permissionDecision`):
  * SUBAGENT context (stdin `agent_type` is non-empty — e.g. `phase-executor`):
        -> `deny`. Autonomous runs are hard-blocked; a subagent cannot answer an
        `ask` prompt anyway. This is the human gate the prose describes.
  * MAIN session: -> `ask`. The human confirms the high-risk action once.
  * Everything else: exit 0 (defer to normal permission rules).

The guard fails OPEN on any parse error — it must never brick the session.

Covers two vectors:
  1. Bash commands: push / PR-merge / release / cluster or `make` deploy &
     rollback / shell writes into the feature-flag dir.
  2. Edit/Write to governance-controlled paths (CLAUDE.md §8 dual-approval and
     §14 triggers): guardrails, the HITL gateway/store, and feature-flag config.

Read-only variants (git status, git tag -l, helm list, kubectl get) are not
matched. See CLAUDE.md §3 / §14 and ADR-0011 / ADR-0015 / ADR-0034.
"""

from __future__ import annotations

import json
import re
import sys

# --- Bash: outward-facing / irreversible commands -------------------------------------
# Anchored to a command boundary (start, or after ; & | newline) to reduce, though not
# eliminate, matches inside quoted strings. A safety guard errs toward over-prompting.
_BOUNDARY = r"(?:^|[\n;&|]|\s)"
HIGH_RISK_CMD = re.compile(
    _BOUNDARY
    + r"""(?:
        git\s+push                              |
        gh\s+pr\s+merge                         |
        gh\s+release\s+create                   |
        git\s+push\s+--tags                      |
        helm\s+(?:upgrade|install|rollback)\b   |
        kubectl\s+(?:apply|delete|rollout)\b    |
        make\s+deploy\b                         |
        make\s+rollback\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# Feature-flag / autonomy mutations written through the shell (ADR-0015).
FLAG_WRITE_CMD = re.compile(
    r"(?:>>?|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|\binstall\b)[^\n]*infrastructure/feature-flags/",
    re.IGNORECASE,
)

# --- Edit/Write: governance-controlled paths (CLAUDE.md §8 / §14) ----------------------
SENSITIVE_PATH = re.compile(
    r"(?:"
    r"infrastructure/feature-flags/"
    r"|src/shared/feature_flags\.py"
    r"|src/guardrails/"
    r"|src/agents/hitl_gateway\.py"
    r"|src/agents/hitl_store\.py"
    r")"
)

_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _is_risky(payload: dict) -> tuple[bool, str]:
    """Return (risky, short-label) for the tool call described by ``payload``."""
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool_name == "Bash":
        command = tool_input.get("command", "") or ""
        if HIGH_RISK_CMD.search(command) or FLAG_WRITE_CMD.search(command):
            return True, "push / merge / release / deploy / rollback / flag-change"
    elif tool_name in _EDIT_TOOLS:
        path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "") or ""
        if SENSITIVE_PATH.search(path):
            return True, "edit to a governance-controlled path (guardrails / HITL / feature flags)"
    return False, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open — never block on a parse failure

    risky, label = _is_risky(payload)
    if not risky:
        return 0  # not high-risk — defer to normal permission rules

    agent_type = (payload.get("agent_type") or "").strip()
    if agent_type:
        decision = "deny"
        reason = (
            f"Blocked: the '{agent_type}' subagent may not perform a high-risk action "
            f"({label}). Autonomous delivery runs stop at this human gate — perform it "
            f"from the main session with explicit approval (F7 / #133; CLAUDE.md §3/§14)."
        )
    else:
        decision = "ask"
        reason = (
            f"High-risk action ({label}). Confirm this is an intended human action "
            f"(F7 / #133; CLAUDE.md §3/§14)."
        )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
