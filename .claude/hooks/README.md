# Claude Code hooks

Project-wide harness hooks, wired in [`.claude/settings.json`](../settings.json) and shared
with the whole team (checked into git).

## `high-risk-action-guard.py` — PreToolUse guard (F7 / issue #133)

A `PreToolUse` hook (matches `Bash`, `Edit`, `Write`, `MultiEdit`, `NotebookEdit`) that moves
the "never autonomously push / merge / release / deploy / change a flag" guarantees from prose
into the harness layer. It closes **F7** (`docs/sdlc/deliver-dryrun-findings.md`): the `/deliver`
skill and its `phase-executor` subagent hold an unscoped `Bash` grant, so those rules were
previously enforced only by instructions.

**Decision policy** (`permissionDecision`):

| Context                                                | High-risk action      | Result                                                            |
| ------------------------------------------------------ | --------------------- | ----------------------------------------------------------------- |
| **Subagent** (`agent_type` set, e.g. `phase-executor`) | yes                   | **`deny`** — hard-blocked; autonomous runs stop at the human gate |
| **Main session**                                       | yes                   | **`ask`** — you confirm once                                      |
| any                                                    | no (safe / read-only) | defer (exit 0) — normal permission rules                          |

> An `ask` decision blocks in a subagent context anyway (a subagent can't answer the prompt), so
> the guard is safe even if `agent_type` is unavailable — the subagent simply can't proceed.

**What counts as high-risk**

- _Bash:_ `git push`, `gh pr merge`, `gh release create`, `helm upgrade|install|rollback`,
  `kubectl apply|delete|rollout`, `make deploy*`, `make rollback`, and shell writes into
  `infrastructure/feature-flags/`. Read-only variants (`git status`, `git tag -l`, `helm list`,
  `kubectl get`) are not matched.
- _Edit/Write:_ governance-controlled paths (CLAUDE.md §8 dual-approval / §14): `src/guardrails/`,
  `src/agents/hitl_gateway.py`, `src/agents/hitl_store.py`, `src/shared/feature_flags.py`,
  `infrastructure/feature-flags/`.

The guard **fails open** — any parse error returns exit 0 (defer), so it can never brick a session.

**Test it**

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push"}}' | python3 .claude/hooks/high-risk-action-guard.py
# → {"hookSpecificOutput": {... "permissionDecision": "ask" ...}}
echo '{"tool_name":"Bash","tool_input":{"command":"git push"},"agent_type":"phase-executor"}' | python3 .claude/hooks/high-risk-action-guard.py
# → {"hookSpecificOutput": {... "permissionDecision": "deny" ...}}
```

**Bypass** (rare, deliberate): comment out the hook in `.claude/settings.json`, or run the command
outside Claude Code. Changes to `settings.json` hooks are re-reviewed by Claude Code on next start
for safety, so a teammate pulling this will be prompted to approve the hook before it activates.
