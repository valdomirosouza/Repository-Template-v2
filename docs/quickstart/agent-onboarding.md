# Agent Onboarding — How Claude Code Starts a Session

**Audience:** Engineers who deploy or supervise Claude Code sessions
**ADR:** ADR-0031 | **Skill:** `skills/sdlc/agent-onboarding.md` | **Issue:** #4

This guide explains the 5-step bootstrap protocol that Claude Code follows at the start
of every session. Understanding it helps you verify the agent is working correctly and
intervene when needed.

---

## Why This Exists

Without a structured bootstrap, an agent starting a new session must reconstruct context
from scratch — reading files it has already read, re-identifying the relevant spec, and
re-loading skills it already knows it needs. This wastes context budget and introduces
inconsistency across sessions.

The protocol defined here makes session startup deterministic and auditable.

---

## The 5-Step Bootstrap (what the agent does)

### Step 1 — Reads CLAUDE.md

The agent reads the full `CLAUDE.md` behavioral contract. You can verify this happened
by checking that the agent's first response references the current version number in
the CLAUDE.md header.

**What to watch for:** If the agent skips this and goes straight to code, prompt it:

> "Before proceeding, please run the agent onboarding protocol from `skills/sdlc/agent-onboarding.md`."

### Step 2 — Reads services.yaml

The agent reads the canonical service registry to understand which services exist,
their languages, and their Kafka topics. This prevents it from touching undocumented
services or creating topics that conflict with existing ones.

### Step 3 — Loads Relevant Skills (max 2)

The agent selects at most two skill files from `skills/` based on the task domain.
Loading more than two simultaneously violates the context budget rules (CLAUDE.md §13.2).

If the agent loads skills you did not expect, ask it to explain why each one is relevant.

### Step 4 — Identifies the GitHub Issue

The agent lists open issues and finds the one for this task. If no issue exists, it
must create one before writing any code. This is a hard SDD invariant.

```bash
# You can check what the agent found:
gh issue list --repo valdomirosouza/Repository-Template-v2 --state open
```

### Step 5 — Confirms the Spec Reference

The agent reads the spec referenced by the issue and checks:

- Status is `Approved` (not `Draft`)
- Acceptance criteria are clear and testable

If no spec exists after two searches, the agent emits a `[HITL-ESCALATE]` block and stops.

---

## Escalation During Bootstrap

If the agent encounters any of the six escalation triggers (CLAUDE.md §14) during
bootstrap — for example, cannot find a spec — it will emit:

```
[HITL-ESCALATE]
reason: spec reference not found after two search attempts
proposed_action: proceed with implementation using inferred requirements
risk_level: high
files_affected: <files that would be written>
awaiting_human_decision: true
```

**Do not approve "proceed with inferred requirements" unless you have explicitly provided
the requirements in the conversation.** Instead, create the spec first.

---

## CLAUDE_SESSION_INIT.md

The `CLAUDE_SESSION_INIT.md` file in the repo root is a compact session primer loaded
alongside `CLAUDE.md`. It provides:

- Repo identity and active branch convention
- A table of the most sensitive code paths (those that trigger escalation)
- A quick ADR index
- A session checklist the agent works through

You can extend it with project-specific context without modifying `CLAUDE.md`.

---

## Verifying a Bootstrap Completed Correctly

After the agent's opening message, check:

| Signal                         | What it means   |
| ------------------------------ | --------------- |
| References CLAUDE.md version   | Step 1 complete |
| Names the affected service     | Step 2 complete |
| Lists one or two skill names   | Step 3 complete |
| Cites a GitHub Issue number    | Step 4 complete |
| Quotes an acceptance criterion | Step 5 complete |

If any signal is missing, ask the agent to complete the missing step before continuing.
