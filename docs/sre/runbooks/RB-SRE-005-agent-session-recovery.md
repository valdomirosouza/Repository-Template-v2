# RB-SRE-005 — Agent Session Recovery

**Owner:** SRE Lead | **Last updated:** 2026-06-05
**Spec:** `specs/ai/long-running-session.md`
**ADR:** ADR-0033
**Related:** RB-003 (HITL Recovery)

---

## When to Use This Runbook

Use when a Claude Code agentic session was interrupted mid-sprint and you need to:

- Inspect the saved checkpoint before resuming
- Force a clean restart by deleting a corrupted checkpoint
- Resume a session that halted with `[HITL-ESCALATE]` due to `plan-corrupted`

---

## 1. Inspect a Checkpoint

### Via Redis CLI

```bash
# List all active session checkpoints
redis-cli KEYS "session:checkpoint:*"

# Read a specific checkpoint
redis-cli GET "session:checkpoint:<session_id>" | jq .

# Check TTL (seconds remaining)
redis-cli TTL "session:checkpoint:<session_id>"
```

### Via local JSON fallback (dev)

```bash
ls .claude/checkpoints/
cat .claude/checkpoints/<session_id>.json | jq .
```

### Key fields to verify

| Field                          | What to check                                                         |
| ------------------------------ | --------------------------------------------------------------------- |
| `current_step`                 | Which sprint index the session was on when interrupted                |
| `completed_steps`              | List of sprint IDs already finished — these will be skipped on resume |
| `sprint_plan.sprint_contracts` | Full list of sprints; verify none are missing                         |
| `updated_at`                   | Timestamp of the last successful save                                 |

---

## 2. Resume an Interrupted Session

An interrupted session (`interrupted` failure type) resumes automatically when restarted
with the same `session_id`. No manual action needed if the checkpoint is intact.

To verify the checkpoint is readable before resuming:

```bash
# Python one-liner to test deserialization
uv run python -c "
import asyncio, json
from src.agents.harness.session_checkpoint import SessionCheckpoint
cp = asyncio.run(SessionCheckpoint.resume('<session_id>'))
print('OK' if cp else 'NOT FOUND')
print(f'step={cp.current_step}, done={len(cp.completed_steps)}' if cp else '')
"
```

---

## 3. Delete a Corrupted Checkpoint (`plan-corrupted`)

When the session halts with:

```
[HITL-ESCALATE]
reason: Checkpoint for session <id> is corrupted: <error>
risk_level: high
awaiting_human_decision: true
```

**Do not resume.** Delete the checkpoint and restart from scratch:

```bash
# Redis
redis-cli DEL "session:checkpoint:<session_id>"

# Local fallback
rm .claude/checkpoints/<session_id>.json
```

After deletion, start a new Claude Code session. The planner will re-generate the
sprint plan from the original task brief.

---

## 4. Force-Expire a Stale Checkpoint

If a checkpoint is from an abandoned session (operator lost context of the task):

```bash
# Reduce TTL to 60 seconds to let it expire naturally
redis-cli EXPIRE "session:checkpoint:<session_id>" 60
```

---

## 5. Handle `context-overflow` or `budget-exceeded`

These failure types are self-reported by the agent before halting. The checkpoint is
saved at the current step boundary. On next session:

1. Provide the same `session_id` to the new session
2. The agent skips completed steps and resumes from `current_step`
3. If the step that caused overflow is the same step again, reduce scope or split it

---

## 6. Escalation

If the checkpoint cannot be recovered and the sprint plan cannot be reconstructed:

1. Collect the checkpoint JSON (or note it is missing)
2. Open a GitHub Issue with label `incident` and the full `[HITL-ESCALATE]` block
3. Escalate to the Tech Lead with: `session_id`, `task_id`, `correlation_id`, last known `current_step`
