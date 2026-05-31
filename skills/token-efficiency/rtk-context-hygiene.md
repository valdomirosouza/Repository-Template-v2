# Skill: RTK Context Hygiene (Token Efficiency — Session Rules)

**Spec:** RTK-001 | **ADR:** ADR-0030 | **Source:** https://github.com/rtk-ai/rtk

## Purpose

Complement RTK command filtering with disciplined context window management.
RTK handles command output (60–80% savings). This skill handles the rest:
file reads, skill loading, response verbosity, and tool selection.

## When to activate

- Start of every Claude Code session in this repository
- Trigger phrase: "new session", "start task", "begin work"

## Rule 1 — Read only what you need

Bad: Read `src/agents/orchestrator/orchestrator.py` (500 lines) to change 3 lines  
Good: Use `head -50` or `grep -n` first to locate the target

```bash
# Locate before reading
rtk grep "def target_function" src/agents/          # find it first
head -80 src/agents/orchestrator/orchestrator.py    # read only the relevant section
```

## Rule 2 — Load skills on demand, not upfront

Bad: Read all 15 skill files at session start  
Good: Load only the skill matching the current task (see §4 Skill Activation Table in CLAUDE.md)

**One task = one skill load maximum**, unless the task genuinely spans two domains.

## Rule 3 — Prefer compact shell commands over built-in tools

Because the PreToolUse hook only applies to Bash tool calls:

| Instead of                | Use                               |
| ------------------------- | --------------------------------- |
| Read tool on a large file | `cat file \| head -100`           |
| Glob tool for file count  | `find src/ -name "*.py" \| wc -l` |
| Read tool on test output  | `rtk pytest tests/unit/ 2>&1`     |

## Rule 4 — Summarize before expanding

When exploring an unfamiliar module:

```bash
rtk smart src/agents/harness/          # 2-line heuristic summary of each file
rtk ls src/agents/                     # compact tree first
# THEN read specific files you need
```

## Rule 5 — Scope git operations tightly

```bash
rtk git diff HEAD~1 src/api/          # diff only changed path, not whole repo
rtk git log -n 5                      # last 5 commits, not full history
rtk git status                        # always use rtk, never raw git status
```

## Rule 6 — Use rtk discover weekly

```bash
rtk discover --since 7               # shows commands with 0% savings from last 7 days
```

Any command appearing repeatedly with 0% savings should get a custom filter in `.rtk/filters.toml`.

## Rule 7 — tee mode for debugging

When a filter produces wrong output, don't re-run raw:

```bash
# RTK saves full output automatically on failure to:
# ~/.local/share/rtk/tee/<timestamp>_<cmd>.log
# Read it without re-executing:
cat ~/.local/share/rtk/tee/$(ls -t ~/.local/share/rtk/tee/ | head -1)
```

## Rule 8 — Token budget awareness

```bash
rtk gain                             # check savings at start of long sessions
rtk gain --graph                     # ASCII graph of last 30 days
```

If `rtk gain` shows < 50% average savings, run `rtk discover` to find what's leaking.

## Session start checklist

```bash
pwd && git branch                    # confirm location and branch
rtk gain                             # check token budget health
rtk git status                       # see what's changed
```
