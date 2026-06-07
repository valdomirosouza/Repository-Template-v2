# ADR-0060 — Task Atomicity & the 2-Skill Budget (decomposition oracle)

**Status:** Accepted
**Date:** 2026-06-07
**Authors:** Valdomiro Souza

---

## Context

The repository already caps skill loading at "≤ 2 relevant skill files per task"
(`CLAUDE.md` §13.2, `skills/sdlc/agent-onboarding.md` Step 3). To date this has been framed
as a **token-efficiency constraint** — a ceiling to respect so context stays lean.

In practice the budget does more than save tokens: when a task _needs_ a third skill to
finish, that is reliable evidence the task is carrying more than one concern. Treated only
as a constraint, the budget gets "worked around" (bulk-loading, or stretching one task
across several artifacts), which defeats both token efficiency and reviewability. ASDD phase
agents already bind their phase skills (ADR-0058; per-phase bindings), but nothing tells an
agent **how finely to cut a unit of work** so the binding stays honest.

We want one rule that decides task granularity for the whole Agentic Spec-Driven Delivery
lifecycle, so a full cycle (rules, guardrails, context, ADR, RFC, harness, tests,
observability) always fits without ever overloading a single task.

## Decision

Adopt **Task Atomicity & the 2-Skill Budget** as the project's **decomposition oracle**.
The directive is authoritative and is embedded in `CLAUDE.md` §4 (with a cross-reference
from §13.2) and summarized in `AGENTS.md`. Its load-bearing rules:

1. **The budget is the decomposition oracle, not a post-hoc constraint.** Before starting
   any task, list the skills it would need to _finish_. ≤ 2 → atomic, declare bindings and
   execute. ≥ 3 → not atomic; **do not load a 3rd skill** — split at the skill boundary into
   child tasks that each need ≤ 2 skills, and recurse until every leaf fits.
2. **One task = one reviewable artifact.** Each atomic task produces exactly one artifact a
   human can review in isolation (one ADR, one RFC, one guardrail module, one harness
   component, one contract, one test file, one spec section). Two unrelated artifacts ⇒ split.
3. **Ambient context never occupies a slot.** `CLAUDE.md`, repo structure, `services.yaml`,
   and already-written ADRs/specs are ambient — every agent loads them regardless. The 2
   slots are reserved purely for domain skills. Governance is never traded for context;
   decompose instead.
4. **Phase coverage check.** A phase is done only when every artifact it owes exists. After
   the last task in a phase, enumerate required artifacts and create a **dedicated atomic
   task** for any not yet produced — never bolt it onto an existing task.
5. **Declare bindings explicitly.** Every task header carries a `## Skills — load before
executing` block (≤ 2). Subagents run in isolated context and load these themselves;
   they do not inherit the parent's skills.
6. **Irreducible coupling → escalate, don't overload.** If a task genuinely cannot drop
   below 3 skills, treat it as a design smell: surface to HITL with the three skills named
   and a proposed split (`[HITL-ESCALATE]`, §14). Never silently load a 3rd skill.

### Cross-cutting control bindings

Compliance, privacy, and security obligations attach to a task by **what it touches**, not
by which phase it lives in, so the per-phase coverage check does not capture them. A
pre-task trigger table binds each obligation to either a domain skill (counts against the
budget) or an ambient ADR/CI gate (does not). Applicability is **conditional** — controls
such as SOX (ADR-0026) apply only in regulatory scope; a per-project applicability matrix
(regulatory scope, data residency, data-subject jurisdictions) is consulted before any
control is treated as mandatory. Firing **3+ control triggers** in one task is itself a
split signal. The trigger table and matrix live in `docs/governance/` (see follow-up task).

## Consequences

**Positive**

- Task granularity is now decidable by a single, testable rule instead of judgment call.
- Every task maps to one reviewable artifact, improving PR review and traceability.
- The full ASDD governance load (rules + guardrails + ADR + RFC + harness + tests +
  observability) is guaranteed to fit, because it is _partitioned across atomic tasks_
  rather than carried by any one.
- Token efficiency is preserved as a side effect, not as the primary mechanism.

**Negative / costs**

- More, smaller tasks and PRs (mitigated: docs-only tasks auto-merge; merge commits keep
  `develop` an ancestor of `main` per ADR-0057/RFC-0001/RFC-0002).
- Authors must enumerate skills up front — a small planning tax that pays back in clarity.

**Neutral**

- Reframes, does not weaken, the existing ≤ 2 rule in `CLAUDE.md` §13.2; no guardrail,
  privacy, security, or SDD invariant is changed.

## Rollout

Tracked as five atomic tasks (this ADR is task 1): #70 ADR (this), #71 CLAUDE.md §4,
#72 AGENTS.md, #73 control-applicability matrix + trigger table, #74 session kickoff +
phase-coverage wiring. The source directive (`task-atomicity-skill-budget-directive.md`,
provided as a working-tree note, never committed) has been **fully absorbed** into the
contract; its content now lives canonically in `CLAUDE.md` §4 and
`docs/governance/control-applicability-matrix.md`.

## References

- Source directive (`task-atomicity-skill-budget-directive.md`, working-tree note, not retained) — fully absorbed; canonical content now in `CLAUDE.md` §4
- `CLAUDE.md` §4 (Skills), §13.2 (token efficiency), §14 (escalation)
- ADR-0058 (Agentic Spec-Driven Delivery), ADR-0026 (SOX), ADR-0027 (ISO 27001), ADR-0029 (DevSecOps pipeline)
