# Skill — Agent Onboarding Protocol

**Owner:** Tech Lead | **Status:** Active | **Last updated:** 2026-06-05
**ADR:** ADR-0031 | **Issue:** #4

Activate this skill at the **start of every Claude Code session** before writing any code,
or when asked to onboard to a new service context.

---

## The 5-Step Session Bootstrap

Execute these steps in order before any implementation work. Do not skip.

### Step 1 — Read CLAUDE.md

```
Read CLAUDE.md in full.
```

- Note the current version number (header line).
- Confirm §14 Agentic Escalation Protocol is loaded into context.
- Identify any domain-specific rules that apply to this task (§10 SOX, §11 ISO 27001, etc.).

### Step 2 — Read services.yaml

```
Read services.yaml (repo root).
```

- Identify all services, their languages, Kafka topics, and API versions.
- Note which service(s) the task will touch.
- If the task affects a service not in `services.yaml`, flag it before proceeding.

### Step 3 — Load Relevant Skills

The **2-skill budget is the decomposition oracle** (CLAUDE.md §4, ADR-0060), not just a
token limit. Before loading, list the skills the task needs to _finish_: **≤ 2** → atomic,
load them and execute; **≥ 3** → the task is too big — **split it at the skill boundary**
into child tasks that each need ≤ 2 skills (never load a 3rd). One task = one reviewable
artifact. Then load **at most two** skill files for the leaf task:

| Task involves…          | Load this skill                                |
| ----------------------- | ---------------------------------------------- |
| PII or personal data    | `skills/privacy/pii.md`                        |
| REST endpoint           | `skills/api/rest-api-design.md`                |
| Tests or coverage       | `skills/engineering/testing-strategy.md`       |
| Deploy or rollback      | `skills/change-management/deploy-rollback.md`  |
| Observability / metrics | `skills/observability/otel-instrumentation.md` |
| Domain model / entity   | `skills/domain/domain-modeling.md`             |
| AI agent action         | `skills/ai/guardrails.md`                      |
| Multi-agent harness     | `skills/ai/harness.md`                         |
| Security / OWASP        | `skills/devsecops/owasp-top10.md`              |
| CI/CD pipeline          | `skills/devsecops/pipeline-security.md`        |
| Spec writing            | `skills/sdlc/spec-lifecycle.md`                |

**Cross-cutting controls.** Before executing any task, run the compliance/privacy/security
control triggers in `docs/governance/control-applicability-matrix.md` — they bind by _what
the task touches_, not its phase. Firing 3+ control triggers is itself a split signal.

**Phase-coverage check (close the loop).** An Agentic SDLC phase is done only when every
artifact it owes exists. After the last task in a phase, enumerate the phase's required
artifacts (rules, guardrails, ADR, RFC, harness wiring, tests, observability) and create a
**dedicated atomic task** for any not yet produced — never bolt it onto an existing task.

### Step 4 — Identify Open GitHub Issues

```bash
gh issue list --repo <org>/<repo> --state open --limit 20
```

- Find the issue that corresponds to this task.
- Confirm a spec reference exists in the issue body (look for `SPEC-NNN` or a `specs/` path).
- If no issue exists: create one before writing any code (SDD invariant — CLAUDE.md §2 Step 4).

### Step 5 — Confirm Spec Reference

Before the first file write:

1. Locate the spec file referenced by the issue (`specs/<domain>/<name>.md`).
2. Read its **Status** field — must be `Approved`. If `Draft`, stop and request approval.
3. Read the acceptance criteria — implementation must satisfy every criterion.
4. If no spec exists after two search attempts → emit `[HITL-ESCALATE]` (CLAUDE.md §14).

---

## Session Primer

At session start, also load `CLAUDE_SESSION_INIT.md` if it exists in the repo root.
It contains repo-specific context that supplements this skill.

---

## Context Budget Rules (from CLAUDE.md §13)

- Load **at most 2 skills per task** (the decomposition oracle — split, don't exceed; §4, ADR-0060); one per domain, never bulk-load.
- Use `grep -n` before `Read` on any file > 100 lines.

---

## Related

- `docs/quickstart/agent-onboarding.md` — human-readable version of this protocol
- `CLAUDE_SESSION_INIT.md` — repo-specific session primer
- `CLAUDE.md §2` — SDD Cycle (human-centric workflow this protocol augments)
- `CLAUDE.md §14` — Agentic Escalation Protocol
- ADR-0031: Agent Onboarding Protocol
