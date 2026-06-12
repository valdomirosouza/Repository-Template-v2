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

The guard fails OPEN on ANY error (parse, wrong types, regex) — it must never
brick or block a session by malfunctioning.

Covers two vectors:
  1. Bash commands: push / PR-merge / release / cluster or `make` deploy &
     rollback / shell writes into the feature-flag dir. The binary may carry a
     path prefix (`/usr/bin/git`) and global options before the subcommand
     (`git -C dir push`, `kubectl --context=x apply`), and may be reached via a
     subshell / `eval` (`$(git push)`); all are matched.
  2. Edit/Write to governance-controlled paths (CLAUDE.md §8 dual-approval and
     §14 triggers): guardrails, the HITL gateway/store, and feature-flag config.

Read-only variants (git status, git tag -l, helm list, kubectl get) are not
matched. See CLAUDE.md §3 / §14 and ADR-0011 / ADR-0015 / ADR-0034.
"""

from __future__ import annotations

import json
import re
import sys

# A high-risk invocation =  <boundary> <optional path/> <binary> <global opts>* <subcommand>
#   boundary : start-of-string OR any char that is not part of a path/word token
#              (so `;`, `|`, `&`, `(`, quotes, backtick, `=`, space all qualify, but a
#              word char does not — `mygit push` must NOT match).
#   path     : optional leading path on the binary (`/usr/bin/git`).
#   opts     : zero or more global options, each optionally taking one argument
#              (`-C dir`, `-c k=v`, `--git-dir=x`) — non-greedy so the subcommand
#              still binds.  This is what catches `git -C dir push`.
#   \b after the subcommand avoids matching `git push-foo` as a prefix.
_BIN = r"(?:^|[^\w/.\-])(?:[\w./\-]*/)?"
_OPTS = r"(?:\s+-\S+(?:\s+[^-\s]\S*)?)*?"


def _cmd(binary: str, subcommand: str) -> str:
    return rf"{_BIN}{binary}{_OPTS}\s+(?:{subcommand})\b"


# Commands whose leading binary only READS: a high-risk token in their arguments (a search
# pattern, an echoed string) is text, not an executed action — so don't flag it. This fixes
# false positives like `grep 'git push' <file>` while still flagging a real action in a later
# segment (`cat x && git push`). Command substitution under a read-only leader is still checked
# (`echo $(git push)` executes the push), see `_command_is_risky`.
_READ_ONLY_LEADERS = frozenset(
    {
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "ag",
        "ack",
        "echo",
        "printf",
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "awk",
        "sort",
        "uniq",
        "wc",
        "ls",
        "find",
        "tree",
        "diff",
        "comm",
        "cut",
        "tr",
        "column",
    }
)
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
_CMD_SUBST = re.compile(r"\$\(|`")


def _leading_token(segment: str) -> str:
    """The bare command name of a segment (skips `VAR=val` prefixes and any path)."""
    for tok in segment.strip().split():
        if "=" in tok and not tok.startswith("-") and "/" not in tok.split("=", 1)[0]:
            continue  # leading environment assignment (FOO=bar cmd …)
        return tok.rsplit("/", 1)[-1]
    return ""


def _command_is_risky(command: str) -> bool:
    """True if any *executed* shell segment is a high-risk action or flag write."""
    for segment in _SEGMENT_SPLIT.split(command):
        seg = segment.strip()
        if not seg:
            continue
        # A read-only inspector's arguments are not executed — unless they contain command
        # substitution, which runs regardless of the outer command.
        if _leading_token(seg) in _READ_ONLY_LEADERS and not _CMD_SUBST.search(seg):
            continue
        if HIGH_RISK_CMD.search(seg) or FLAG_WRITE_CMD.search(seg):
            return True
    return False


HIGH_RISK_CMD = re.compile(
    "|".join(
        (
            _cmd("git", r"push"),
            _cmd("gh", r"pr\s+merge|pr\s+create|pr\s+ready|release\s+create"),
            _cmd("helm", r"upgrade|install|rollback"),
            _cmd("kubectl", r"apply|delete|rollout"),
            _cmd("make", r"deploy|rollback"),
        )
    ),
    re.IGNORECASE,
)

# Feature-flag / autonomy mutations written through the shell (ADR-0015).
FLAG_WRITE_CMD = re.compile(
    r"(?:>>?|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|\binstall\b)[^\n]*infrastructure/feature-flags/",
    re.IGNORECASE,
)

# Edit/Write to governance-controlled paths (CLAUDE.md §8 / §14).
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

_CMD_LABEL = "push / PR-create / PR-merge / release / deploy / rollback / flag-change"
_PATH_LABEL = "edit to a governance-controlled path (guardrails / HITL / feature flags)"


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _is_risky(payload: dict) -> tuple[bool, str]:
    """Return (risky, short-label). Never raises — callers rely on fail-open."""
    try:
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            return False, ""

        if tool_name == "Bash":
            command = _as_str(tool_input.get("command"))
            if _command_is_risky(command):
                return True, _CMD_LABEL
        elif tool_name in _EDIT_TOOLS:
            path = _as_str(tool_input.get("file_path")) or _as_str(tool_input.get("notebook_path"))
            if SENSITIVE_PATH.search(path):
                return True, _PATH_LABEL
    except Exception:
        return False, ""  # fail open
    return False, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0

        risky, label = _is_risky(payload)
        if not risky:
            return 0  # not high-risk — defer to normal permission rules

        agent_type = str(payload.get("agent_type") or "").strip()
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
    except Exception:
        return 0  # fail open — never block on an internal error
    return 0


if __name__ == "__main__":
    sys.exit(main())
