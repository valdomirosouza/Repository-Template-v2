# ADR-0031: Agent Onboarding Protocol

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Skill:** `skills/sdlc/agent-onboarding.md`
**Issue:** #4
**Related ADRs:** ADR-0030 (RTK Token Efficiency), ADR-0034 (Agentic Escalation Protocol)

---

## Context

Each Claude Code session starts cold — the agent has no memory of previous sessions
and must reconstruct context from the codebase. Without a defined bootstrap protocol,
agents spend 20–40% of their context budget re-reading files they already know they
need, and occasionally miss critical behavioral contracts (CLAUDE.md), service
boundaries (services.yaml), or spec references.

This was identified as Gap 1.1–1.3 in the _2026 Agentic Coding Trends Compliance Plan_:

- **Gap 1.1** — No agent-awareness in the onboarding path
- **Gap 1.2** — No dynamic session bootstrap protocol
- **Gap 1.3** — SDD Cycle (CLAUDE.md §2) is human-centric with no machine-readable entry point

---

## Decision

Define a **5-step Agent Onboarding Protocol** executed at the start of every Claude Code
session before any file writes:

1. Read `CLAUDE.md` — load behavioral contract and escalation rules
2. Read `services.yaml` — establish service registry awareness
3. Load ≤ 2 relevant skill files based on task domain
4. Identify the GitHub Issue for the task (create one if absent)
5. Confirm spec reference is `Approved` before the first write

Materialise the protocol as:

- `skills/sdlc/agent-onboarding.md` — machine-readable skill (agent loads and follows)
- `docs/quickstart/agent-onboarding.md` — human-readable guide for supervisors
- `CLAUDE_SESSION_INIT.md` — compact repo-specific primer at the repo root

Update `CLAUDE.md §2` to reference the bootstrap as a pre-step to the SDD cycle.

---

## Consequences

**Positive:**

- Deterministic session startup — the same five steps every time, auditable.
- Reduces context waste from redundant file reads.
- Ensures escalation protocol (ADR-0034) is always loaded before implementation begins.
- Supervisors have a checklist to verify bootstrap completeness.

**Neutral:**

- Adds ~5 minutes of overhead to session start for complex repos.
  Mitigated by the context budget rules (CLAUDE.md §13.2) — max two skills loaded.
- `CLAUDE_SESSION_INIT.md` must be kept short (< 80 lines) to avoid consuming
  disproportionate context on every session.

**Risk:**

- Agents may skip the protocol on short tasks. Mitigated by the CLAUDE.md §2 update
  making it a mandatory pre-step, and by `CLAUDE_SESSION_INIT.md` being the first
  file recommended for reading in the session.
