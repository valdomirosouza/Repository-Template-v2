# Skill: RTK Setup (Token Efficiency — Install)

**Spec:** RTK-001 | **ADR:** ADR-0030 | **Source:** https://github.com/rtk-ai/rtk

## Purpose

Install RTK (Rust Token Killer) and activate the Claude Code PreToolUse hook so that
all bash tool calls are automatically filtered before reaching the LLM context window.
Run this skill ONCE per developer machine. After setup, all savings are automatic.

## When to activate

- First time a developer clones the repository
- When onboarding a new team member
- After a clean machine rebuild
- Trigger phrase: "set up token savings", "install rtk", "reduce tokens"

## Prerequisite check

```bash
rtk --version 2>/dev/null || echo "RTK not installed"
```

If RTK is already installed and shows version ≥ 0.28.0, skip to "Verify Hook".

## Install

### macOS (recommended)

```bash
brew install rtk
```

### Linux / WSL

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

### Cargo (cross-platform fallback)

```bash
cargo install --git https://github.com/rtk-ai/rtk
```

## Activate Claude Code Hook

```bash
rtk init -g          # Installs PreToolUse hook + RTK.md into Claude Code settings
```

**Restart Claude Code after this step.** The hook rewrites bash commands transparently.

## Verify Hook

```bash
rtk --version        # → rtk 0.x.x
rtk gain             # → shows token savings stats (NOT "command not found")
```

## Scope note (important)

The hook rewrites **Bash tool calls only**. Claude Code built-in tools (Read, Grep, Glob)
bypass the hook. To get RTK filtering on file reads, use shell commands:

- `cat file.py` → filtered ✓ (bash tool → hook applies)
- Read tool → NOT filtered ✗ (built-in tool → hook bypassed)

Use `rtk read file.py` explicitly when you want aggressive filtering on large files.

## Post-install: apply project filters

After installing RTK globally, apply this repo's custom `.rtk/filters.toml`:

```bash
# Already present in repo root — no action needed.
# RTK auto-loads .rtk/filters.toml from the working directory.
rtk discover         # Shows which commands in recent sessions had 0% savings
```
