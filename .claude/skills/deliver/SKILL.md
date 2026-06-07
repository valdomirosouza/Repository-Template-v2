---
name: deliver
description: >-
  Drive ONE feature spec through the full 15-phase Agentic Spec-Driven Delivery
  workflow (ADR-0058) as a governed DRY-RUN. Trigger on "deliver", "deliver a spec",
  "15-phase", "Agentic SDLC", "dry-run delivery", or "delivery report". Usage:
  /deliver <path-to-spec.md>. Produces a plan, a decomposed backlog, per-phase
  execution via the phase-executor subagent, and a FINAL-REPORT with
  requirement-traceability, agent timing, and a human-vs-agent speedup ratio.
  Never invents a spec; never causes real side-effects.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash, Task
---

# /deliver — Agentic Spec-Driven Delivery (dry-run orchestrator)

You orchestrate one feature spec through the repo's **15-phase Agentic Spec-Driven
Delivery** lifecycle, delegating each phase to the `phase-executor` subagent. This is a
**thin** orchestrator: it points to repo knowledge and does **not** restate phase criteria —
the executor reads them per phase.

`$ARGUMENTS` is the path to the spec file. **If `$ARGUMENTS` is empty, ask the user for the
spec path and stop — never invent or fabricate a spec.** If the path does not exist, report
that and stop (the spec must exist before delivery).

## Ground truth (read these; do not restate them in this file)

- `CLAUDE.md` — the behavioural contract (§2 SDD cycle, §3 inviolable rules, §14 escalation).
- `docs/process/gates/phase-gates.yaml` — the **authoritative** 15 phase definitions, required
  artifacts, required approvals, allowed/prohibited actions, exit criteria.
- `docs/process/WORKFLOW.md` — the human-readable 15-phase lifecycle (ADR-0058).
- `specs/sdlc/development-lifecycle.md` — the 5-stage view (Spec→Implement→Verify→Stage→Produce).
- `docs/adr/README.md` — ADR index, for phase→ADR mapping (esp. ADR-0058, 0052, 0034, 0011).
- `src/agents/hitl_gateway.py` — where HITL interception happens (ADR-0011; timeout always rejects).
- `Makefile` / `README.md` — the real validation targets used for evidence.

## The 15 phases (exact names, from phase-gates.yaml — run in dependency order)

`0` Intake & Prioritization · `1` Conception · `2` Discovery · `3` Grooming ·
`4` Specification · `5` Architecture · `6` Development · `7` Code Review · `8` Testing ·
`9` Security & DevSecOps · `10` AI Safety & Agent Governance · `11` Observability &
Operational Readiness · `12` Release Candidate · `13` Production Deployment ·
`14` Post-Deployment & Learn.

Phase 10 is **conditional** (`ai_or_agent_change`): if the spec touches neither `src/agents/`
nor `src/guardrails/` nor a new `action_type`/autonomy, record it `N/A` and continue without a gate.

## Procedure

Let `SLUG` = the spec filename without extension. All output goes under `reports/<SLUG>/`.

### Phase 0 — Plan, then STOP at the first HITL gate

1. Read `CLAUDE.md`, the spec at `$ARGUMENTS`, `specs/sdlc/development-lifecycle.md`, and
   `docs/process/gates/phase-gates.yaml`.
2. Write `reports/<SLUG>/00-plan.md`: problem summary, risk class, the 15-phase plan with the
   governing ADR(s) per phase, the guardrails in scope, and the dry-run evidence strategy.
3. Decompose the spec into `reports/<SLUG>/backlog.yaml` — a list of items, each with:
   `id`, `title`, `phase` (0–14), `depends_on` (list of ids), `adr_refs` (list),
   `acceptance` (testable criteria), `estimate_tshirt` (XS|S|M|L|XL).
4. Emit a HITL gate and **STOP** before executing any phase:
   `HITL-GATE phase=0 reason="plan approval required before execution"`. In dry-run, after
   recording the gate, proceed and log `HITL: auto-approved (dry-run)` with the plan payload.

### Phases 1–14 — delegate each to the phase-executor subagent

For each phase in dependency order, launch the subagent with a **narrow** brief via the Task tool:

```
Task(subagent_type="phase-executor", description="Phase <N> — <name>", prompt="""
PHASE: <N> — <exact phase name>
SPEC: $ARGUMENTS
SLUG: <SLUG>
BACKLOG_IDS: <ids whose phase == N>
GOVERNING_ADRS: <from phase-gates.yaml / docs/adr/README.md>
GATE_CRITERIA: read docs/process/gates/phase-gates.yaml id=<N> (required_artifacts,
  required_approvals, exit_criteria, allowed/prohibited actions)
GUARDRAILS: CLAUDE.md §3 + src/guardrails/ relevant to this phase
MODE: DRY-RUN — no real side-effects. Validate using the repo's own make targets and tee
  logs into reports/<SLUG>/logs/<N>-<slug>.log
Return: artefacts produced (paths under reports/<SLUG>/), commands run, evidence excerpts
  (≤20 lines), gate PASS/FAIL with reason, and per-task wall-clock (start/end ISO-8601).
""")
```

Record each task's **start and end timestamps** (the orchestrator brackets each Task call).

### HITL enforcement (every phase boundary + every intercepted action)

At each phase boundary, and for any action `src/agents/hitl_gateway.py` would intercept
(consequential/real-world effects — deploy, release, outbound messages, ACL/flag changes),
**PAUSE** and emit a gate line. In **dry-run**, do not block: log
`HITL: auto-approved (dry-run) — payload: <what would have needed a human>` and append it to
the open-HITL list. **Never silently bypass a gate** (CLAUDE.md §14, ADR-0011/0034).

### Dry-run invariants (hard rules)

- **No real side-effects:** no deploy, no `git push`/release, no outbound messages, no
  production writes, no ACL/permission/feature-flag changes, no autonomy changes.
- Evidence = running the repo's **own** validation targets and tee-ing output:
  `make lint-python`, `make test-unit-python`, `make test-security-python`,
  `make check-control-bindings`, `make smoke`/`make doctor` as relevant per phase →
  `reports/<SLUG>/logs/`.
- If a phase would require an irreversible/HITL action, simulate + log it; do not perform it.

### FINAL-REPORT

Write `reports/<SLUG>/FINAL-REPORT.md` containing, in order:

1. **Summary + gate results** — one line per phase: phase, PASS/FAIL/N-A, gate, human-equiv approver.
2. **Requirement-traceability table** — `| Criterion | Phase | ADR(s) | Evidence (log/path) |`
   (one row per acceptance criterion from the backlog/spec).
3. **Task/sub-task table** —
   `| ID | Task | Phase | ADRs | Agent wall-clock | Human-equiv estimate | Status |`
   - _Agent wall-clock_ = end − start from the recorded timestamps.
   - _Human-equiv estimate_ = from `estimate_tshirt`: **XS≈0.5h · S≈2h · M≈4h · L≈8h · XL≈24h**,
     and **clearly label the column an ESTIMATE**.
   - End with **totals** for both columns and a **speedup ratio** (human-equiv ÷ agent wall-clock).
4. **Evidence appendix** — log excerpts, **≤ 20 lines each**, referencing files in `logs/`.
5. **Open-HITL-items list** — every gate that would need a real human, with its payload.

## Guardrails for the orchestrator itself

- One spec per invocation. Do not modify product code under `src/` (this is delivery
  orchestration, not implementation).
- Honour `CLAUDE.md §14` escalation triggers; if one fires, emit `[HITL-ESCALATE]` and stop.
- Respect the 2-skill budget per task (ADR-0060) when briefing the executor.
