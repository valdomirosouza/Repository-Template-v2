# Spec — Long-Running Agent Session Durability

**Status:** Approved | **Owner:** Tech Lead | **Last updated:** 2026-06-05
**ADR references:** ADR-0033 (Long-Running Agent Session Durability), ADR-0014 (Multi-Agent Harness)
**Issue:** #5

---

## 1. Purpose

Define how agentic sessions that span multiple Claude Code invocations persist state,
recover from interruptions, and resume mid-sprint without data loss.

---

## 2. Checkpoint Format

A `SessionCheckpoint` captures the full state needed to resume a sprint:

```json
{
  "session_id": "<uuid>",
  "task_id": "<uuid>",
  "sprint_plan": {
    "task_id": "<uuid>",
    "detailed_description": "<string>",
    "sprint_contracts": [
      {
        "sprint_id": "<uuid>",
        "objectives": ["<string>"],
        "success_criteria": ["<string>"],
        "task_type": "planned | net_new | papercut | tech_debt"
      }
    ],
    "ai_feature_opportunities": ["<string>"]
  },
  "current_step": 0,
  "completed_steps": ["<sprint_id>"],
  "created_at": "<ISO-8601>",
  "updated_at": "<ISO-8601>",
  "correlation_id": "<string | null>"
}
```

### 2.1 task_type Field (Sprint Contract Extension)

Each `SprintContract` carries a `task_type` to enable productivity tracking (Issue #7):

| Value       | Meaning                                                    |
| ----------- | ---------------------------------------------------------- |
| `planned`   | Work specified in the original brief                       |
| `net_new`   | Additive work identified during the session (not in brief) |
| `papercut`  | Small quality-of-life fix discovered opportunistically     |
| `tech_debt` | Refactor or cleanup without new functionality              |

---

## 3. Storage Backend

| Environment                   | Backend                                              | TTL    |
| ----------------------------- | ---------------------------------------------------- | ------ |
| Production / staging          | Redis (`session:checkpoint:{session_id}`)            | 7 days |
| Local dev (Redis unavailable) | JSON file at `.claude/checkpoints/{session_id}.json` | No TTL |

The Redis key is namespaced under `session:checkpoint:` to avoid collisions with
HITL and request store keys.

---

## 4. Resume Protocol

On session start, the agent MUST:

1. Check for an existing checkpoint: `SessionCheckpoint.resume(session_id)`
2. If found:
   a. Log the checkpoint metadata (session_id, current_step, completed_steps)
   b. Skip all `completed_steps` sprint IDs
   c. Resume from `current_step`
3. If not found: begin a new sprint plan from scratch

---

## 5. Failure Taxonomy

| Failure type       | Definition                                                            | Recovery action                                         |
| ------------------ | --------------------------------------------------------------------- | ------------------------------------------------------- |
| `interrupted`      | Session terminated mid-step (process kill, timeout, context overflow) | Resume from last checkpoint                             |
| `plan-corrupted`   | Checkpoint JSON is invalid or sprint_contracts is empty               | Emit `[HITL-ESCALATE]`; do not auto-recover             |
| `context-overflow` | LLM context window exceeded mid-sprint                                | Checkpoint current step; start new session at next step |
| `budget-exceeded`  | Token or cost budget exhausted                                        | Checkpoint; notify operator; await budget increase      |

---

## 6. Checkpoint Lifecycle

```
plan() called
    └─ save(checkpoint, step=0)           ← before any execution

step N begins
    └─ save(checkpoint, step=N)           ← current_step updated

step N completes
    └─ save(checkpoint, completed=[...N]) ← step added to completed_steps

all steps done
    └─ delete(session_id)                 ← checkpoint cleaned up on success
```

On failure at step N, the next session resumes at step N (not N+1).

---

## 7. Acceptance Criteria

- [ ] `SessionCheckpoint.save()` writes to Redis with TTL=7d; falls back to local JSON
- [ ] `SessionCheckpoint.resume()` returns `None` if no checkpoint exists
- [ ] Planner saves checkpoint before first sprint execution
- [ ] Planner updates `completed_steps` after each sprint completes
- [ ] `plan-corrupted` failure emits `[HITL-ESCALATE]` — never silently discarded
- [ ] Unit test coverage ≥ 80% (`tests/unit/agents/test_session_checkpoint.py`)
- [ ] Runbook RB-SRE-005 covers manual checkpoint inspection and deletion
