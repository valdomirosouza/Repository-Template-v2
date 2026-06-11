# ADR-0033: Long-Running Agent Session Durability

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Spec:** `specs/ai/long-running-session.md`
**Issue:** #5
**Related ADRs:** ADR-0014 (Multi-Agent Harness), ADR-0017 (Agent Memory Architecture), ADR-0034 (Escalation Protocol)

---

## Context

In `harness_mode=full`, the PlannerAgent generates a multi-sprint plan before any
implementation begins. If the Claude Code session is interrupted — due to context
overflow, token budget exhaustion, network failure, or manual termination — all
Planner output is lost. The next session must re-plan from scratch, wasting tokens
and potentially producing a different sprint decomposition.

As task horizons extend from minutes to hours and eventually to days (as described
in the _2026 Agentic Coding Trends Report_), this lack of durability becomes a
reliability blocker. Identified as Gaps 3.1–3.3 in the compliance plan.

The existing `src/memory/` layer handles session-level conversational memory (TTL=24h)
but has no concept of a multi-sprint execution plan with step-level progress tracking.

---

## Decision

Introduce a `SessionCheckpoint` abstraction in `src/agents/harness/session_checkpoint.py`:

- **Storage:** Redis at `session:checkpoint:{session_id}` with TTL=7 days;
  JSON file fallback at `.claude/checkpoints/{session_id}.json` when Redis is unavailable.
- **Schema:** session_id, task_id, sprint_plan (full `ProductSpec`), current_step index,
  completed_steps list, timestamps, correlation_id.
- **Lifecycle:** save before first execution → update after each step completes →
  delete on full success.
- **Resume:** on session start, `SessionCheckpoint.resume(session_id)` loads state
  and skips already-completed sprints.
- **Failure taxonomy:** four named failure modes — `interrupted`, `plan-corrupted`,
  `context-overflow`, `budget-exceeded` — each with a defined recovery action.
  `plan-corrupted` always triggers `[HITL-ESCALATE]`; no silent auto-recovery.

The `SprintContract` model is extended with a `task_type` field
(`planned | net_new | papercut | tech_debt`) to support productivity tracking (Issue #7).

---

## Consequences

**Positive:**

- Long-running sessions survive interruptions without data loss.
- Operators can inspect checkpoint state directly in Redis or via the RB-SRE-005 runbook.
- `task_type` field enables ROI measurement of "net-new" vs "planned" work.
- Redis TTL=7d aligns with the sprint horizon; local fallback preserves devX without infra.

**Neutral:**

- Adds a Redis key per active session. At 1,000 concurrent sessions the memory footprint
  is < 10 MB (checkpoint payloads are typically 2–8 KB).
- The `session_id` must be injected by the operator or derived from the Claude Code
  session env var (`CLAUDE_SESSION_ID`). No auto-detection.

**Risk:**

- A `plan-corrupted` checkpoint causes a session to halt with `[HITL-ESCALATE]` rather
  than auto-recovering. This is intentional — silent recovery from a corrupted plan
  could cause the agent to re-execute already-completed steps with real-world effects.
  Operators can manually delete the checkpoint via RB-SRE-005 to force a clean restart.
- The local JSON fallback has no TTL and must be cleaned up manually. The `.claude/`
  directory is `.gitignore`d; checkpoints are never committed.
