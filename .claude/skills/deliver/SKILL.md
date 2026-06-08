---
name: deliver
description: >-
  Drive ONE feature spec through the full 15-phase Agentic Spec-Driven Delivery
  workflow (ADR-0058) in one of two modes: DRY-RUN (governed simulation, no real
  side-effects) or CODE (real implementation into the working tree, still stopping
  at every human gate). Trigger on "deliver", "deliver a spec", "15-phase",
  "Agentic SDLC", "dry-run delivery", or "delivery report". Usage:
  /deliver [dry-run|code] <path-to-spec.md> (mode defaults to dry-run if omitted).
  Produces a plan, a decomposed backlog, per-phase execution via the phase-executor
  subagent, and a FINAL-REPORT with requirement-traceability, agent timing, and a
  human-vs-agent speedup ratio. Never invents a spec; never autonomously merges,
  pushes, releases, deploys, or changes autonomy flags.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash, Task
---

# /deliver — Agentic Spec-Driven Delivery orchestrator (DRY-RUN | CODE)

You orchestrate one feature spec through the repo's **15-phase Agentic Spec-Driven
Delivery** lifecycle, delegating each phase to the `phase-executor` subagent. This is a
**thin** orchestrator: it points to repo knowledge and does **not** restate phase criteria —
the executor reads them per phase.

## Argument parsing — mode + spec path

`$ARGUMENTS` is `[<mode>] <path-to-spec.md>`, where `<mode>` ∈ {`dry-run`, `code`}
(case-insensitive; `dryrun`/`dry_run` accepted as aliases for `dry-run`).

1. Split `$ARGUMENTS` on whitespace. If the **first** token is a recognised mode keyword,
   `MODE` = that keyword and the remaining token is `SPEC`. Otherwise `MODE` = `dry-run`
   (the safe default) and the whole of `$ARGUMENTS` is `SPEC`.
2. **If no spec path remains, ask the user for the spec path and stop** — never invent or
   fabricate a spec. If the path does not exist, report that and stop (the spec must exist
   before delivery).
3. Echo the resolved mode and spec back to the user before doing anything, e.g.
   `Mode: CODE · Spec: specs/foo.md`. For `code`, also state the gate boundary up front
   (see **Modes** below) so the human knows where execution will pause.

## Modes

| Mode                  | What the executor does                                                                                                                      | Writes to                                                                                                     | Validation                                                                                                     | Human gates                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **DRY-RUN** (default) | Drafts each phase's artefact into the report sandbox; simulates every gated action                                                          | `reports/<SLUG>/` **only** — never `src/`, `tests/`, `docs/`, `infrastructure/`, `.github/`                   | Runs the repo's read-only validation targets for evidence                                                      | Auto-approved **and logged** (`HITL: auto-approved (dry-run)`); never silently bypassed               |
| **CODE**              | Implements the spec for real: writes code, tests, ADRs, docs, and migrations into their canonical locations; runs the real validation suite | The **real working tree** (`src/`, `tests/`, `docs/adr/`, `docs/`, migrations, etc.) — **local, uncommitted** | Runs the real lint/test/security/contract targets; a failing required gate **stops** that phase (`gate: FAIL`) | **Enforced for real** — the run **STOPS** at every human gate and never proceeds past it autonomously |

**CODE-mode hard boundary (non-negotiable, CLAUDE.md §3, §14; ADR-0011/0034).** Even in
CODE mode you implement and prepare, but you **never** autonomously perform an outward-facing
or irreversible action. The run **STOPS and waits for explicit human approval** at every one
of these gates and does not continue past it on its own:

- `git push`, opening/merging a PR, creating a tag or GitHub Release (Phases 7, 12, 13).
- Any deploy, rollback, or canary promotion (Phases 12–13).
- Any feature-flag / autonomy / ACL / permission change (ADR-0015).
- Any action `src/agents/hitl_gateway.py` would intercept, or any `CLAUDE.md §14` trigger
  (e.g. modifying `>3` ADRs, touching `src/guardrails/` or `hitl_gateway.py`, coverage
  dropping `<75%`, a missing spec after two searches).

In CODE mode these are **real STOPs** (emit the gate line, stop file writes, wait). In DRY-RUN
they are simulated-and-logged. In **neither** mode do you push, merge, release, deploy, or
change a flag without a human explicitly approving in this session.

## Ground truth (read these; do not restate them in this file)

- `CLAUDE.md` — the behavioural contract (§2 SDD cycle, §3 inviolable rules, §14 escalation).
- `docs/process/gates/phase-gates.yaml` — the **authoritative** 15 phase definitions, required
  artifacts, required approvals, allowed/prohibited actions, exit criteria.
- `docs/process/WORKFLOW.md` — the human-readable 15-phase lifecycle (ADR-0058).
- `specs/sdlc/development-lifecycle.md` — the 5-stage view (Spec→Implement→Verify→Stage→Produce).
- `docs/adr/README.md` — ADR index, for phase→ADR mapping (esp. ADR-0058, 0052, 0034, 0011).
- `src/agents/hitl_gateway.py` — where HITL interception happens (ADR-0011; timeout always rejects).
- `Makefile` / `README.md` — the real validation targets used for evidence.
- `specs/SPEC-TEMPLATE.md` — the canonical spec template; well-formed specs follow it and its
  `§N → phase` map mirrors this procedure. If the spec is missing key sections, note the gap in
  the affected phase rather than inventing content.

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
   `docs/process/gates/phase-gates.yaml`. **Record the tracked-tree baseline** now:
   `git status --porcelain` → `reports/<SLUG>/logs/00-tree-baseline.txt` (the set of files
   already dirty before the run; used by the DRY-RUN snapshot-and-restore invariant below).
2. Write `reports/<SLUG>/00-plan.md`: the resolved `MODE`, problem summary, risk class, the
   15-phase plan with the governing ADR(s) per phase, the guardrails in scope, the evidence
   strategy, and — for `code` — the list of human gates where the run will STOP.
3. Decompose the spec into `reports/<SLUG>/backlog.yaml` — a list of items, each with:
   `id`, `title`, `phase` (0–14), `depends_on` (list of ids), `adr_refs` (list),
   `acceptance` (testable criteria), `estimate_tshirt` (XS|S|M|L|XL).
4. Emit a HITL gate and **STOP** before executing any phase:
   `HITL-GATE phase=0 reason="plan approval required before execution"`.
   - **DRY-RUN:** after recording the gate, proceed and log `HITL: auto-approved (dry-run)`
     with the plan payload.
   - **CODE:** this is a **real STOP** — present the plan + backlog + gate list and **wait for
     the human to approve** before launching any phase. Do not begin Phase 1 until approved.

### Phases 1–14 — delegate each to the phase-executor subagent

For each phase in dependency order, launch the subagent with a **narrow** brief via the Task tool:

```
Task(subagent_type="phase-executor", description="Phase <N> — <name>", prompt="""
PHASE: <N> — <exact phase name>
SPEC: <SPEC>
SLUG: <SLUG>
MODE: <DRY-RUN | CODE>   # emit the CANONICAL upper-case token (normalise dry-run/dryrun/code first)
BACKLOG_IDS: <ids whose phase == N>
GOVERNING_ADRS: <from phase-gates.yaml / docs/adr/README.md>
GATE_CRITERIA: read docs/process/gates/phase-gates.yaml id=<N> (required_artifacts,
  required_approvals, exit_criteria, allowed/prohibited actions)
GUARDRAILS: CLAUDE.md §3 + src/guardrails/ relevant to this phase
MODE CONTRACT:
  - DRY-RUN — no real side-effects. Draft artefacts into reports/<SLUG>/ only; never touch
    src/, tests/, docs/, infrastructure/, .github/. Simulate-and-log every gated action.
  - CODE — implement for real into the canonical locations (src/, tests/, docs/adr/, docs/,
    migrations). Run the real validation suite; a failing required gate ⇒ gate: FAIL.
    NEVER push/merge/tag/release/deploy or change a flag/ACL/autonomy — return those as a
    BLOCKED human gate for the orchestrator to STOP on. Honour every CLAUDE.md §14 trigger
    and any action src/agents/hitl_gateway.py would intercept as a real STOP.
EVIDENCE: validate with the repo's own make targets and tee logs into
  reports/<SLUG>/logs/<N>-<slug>.log
Return: artefacts produced (real paths in CODE / reports/<SLUG>/ in DRY-RUN), commands run,
  evidence excerpts (≤20 lines), gate PASS/FAIL/N-A/BLOCKED (DRY-RUN Phase 6 may be SIMULATED)
  with reason, any human gate hit (with payload), `restored` (DRY-RUN tracked files reverted, or
  none), and per-task wall-clock (start/end ISO-8601).
""")
```

Record each task's **start and end timestamps** (the orchestrator brackets each Task call).
In **CODE** mode, when an executor returns `gate: BLOCKED` for a human gate (push/merge/
release/deploy/flag-change or a §14 trigger), **STOP the run**, surface the gate line and its
payload, and wait for explicit human approval before continuing to the next phase.

### HITL enforcement (every phase boundary + every intercepted action)

At each phase boundary, and for any action `src/agents/hitl_gateway.py` would intercept
(consequential/real-world effects — deploy, release, outbound messages, ACL/flag changes),
**PAUSE** and emit a gate line. **Never silently bypass a gate** (CLAUDE.md §14, ADR-0011/0034).

- **DRY-RUN:** do not block — log
  `HITL: auto-approved (dry-run) — payload: <what would have needed a human>` and append it to
  the open-HITL list.
- **CODE:** this is a **real STOP**. Emit the gate line, halt file writes, surface the payload,
  and wait for the human to approve/modify/cancel in this session before proceeding. Never
  auto-approve a gate in CODE mode.

### Mode invariants (hard rules)

**Both modes:**

- **Never autonomously** `git push`, open/merge a PR, tag, release, deploy, roll back, or
  change a feature-flag/ACL/autonomy setting — these always require an explicit human gate
  (CLAUDE.md §3/§14; ADR-0011/0015/0034). DRY-RUN simulates-and-logs them; CODE STOPs on them.
- Evidence = running the repo's **own** validation targets and tee-ing output:
  `make lint-python`, `make test-unit-python`, `make test-security-python`,
  `make check-control-bindings`, `make smoke`/`make doctor` as relevant per phase →
  `reports/<SLUG>/logs/`.
- One spec per invocation; honour the 2-skill budget per task (ADR-0060).

**DRY-RUN only:**

- **No real side-effects:** all artefacts stay under `reports/<SLUG>/`; never write `src/`,
  `tests/`, `docs/`, `infrastructure/`, `.github/`. Simulate every irreversible/HITL action.
- **Side-effect-safe validation (snapshot & restore).** The repo's validation targets can
  _incidentally_ mutate **tracked** files — e.g. `make lint-python` → `detect-secrets` rewrites
  `.secrets.baseline`'s `generated_at`; `make test-*`/`uv run` may rewrite `uv.lock` drift. These
  are real tracked-tree writes and violate the DRY-RUN invariant. Therefore:
  1. **Before** launching any phase, the orchestrator records a baseline `git status --porcelain`
     (the set of files already dirty — typically empty, but may contain unrelated WIP).
  2. **After** the run (and ideally after each make-running phase), compute the **delta**: tracked
     files that were _clean at baseline_ but became dirty during the run, and restore exactly
     those with `git checkout -- <path>`. Also remove any **new untracked** files a target wrote
     outside the sandbox (e.g. `sbom.cyclonedx.json`, `.coverage`) — `git checkout` does not touch
     untracked files, so a tracked-only restore leaves these behind. The gitignored
     `reports/<SLUG>/` sandbox is the only intended output and is **always** left in place.
  3. **Never** revert a file that was already dirty at baseline (pre-existing WIP) — restore the
     delta only. End the run by asserting the tracked tree equals the baseline.
  4. **This snapshot/restore is DRY-RUN-only.** It is the orchestrator's job; the per-phase
     executor restores what _it_ dirtied, and this close-out is the authoritative backstop against
     the Phase-0 baseline. In **CODE** the working-tree changes are the deliverable — see below.

**CODE only:**

- Implementation **is** the deliverable: write real code/tests/ADRs/docs/migrations into their
  canonical locations (local, **uncommitted**). Required validation gates are enforced for
  real — a failing lint/test/security/coverage gate is a `FAIL`, not a note.
- Keep guardrails unmodified or strengthened, never weakened. Touching `src/guardrails/` or
  `src/agents/hitl_gateway.py` trips a §14 dual-approval STOP.
- **Never `git checkout`/revert/`git clean` the working tree in CODE** — the changes ARE the
  deliverable; the snapshot/restore rule above is **DRY-RUN-only**. The one thing to reconcile is
  _incidental_ tooling churn (e.g. `.secrets.baseline` timestamp): leave it if it belongs with the
  change, revert just that file if it doesn't — never touch the implemented `src/`/`tests/` edits.
- Leave changes in the working tree **uncommitted and unstaged** for human review (no `git add`/
  commit/push). The human reviews the tree and drives Phases 7/12/13 (review-merge, release,
  deploy) themselves.
- Beyond the working-tree implementation, cause **no** real-world side-effects at all — no
  outbound calls, no writes outside the repo, no external mutation — not just the named
  push/merge/deploy/flag actions.

### FINAL-REPORT

Write `reports/<SLUG>/FINAL-REPORT.md` containing, in order:

0. **Run header** — `MODE` (DRY-RUN | CODE), spec path, SLUG, (DRY-RUN) the tracked files restored
   at close-out, and (CODE) the list of human gates the run STOPPED at and their resolution.
1. **Summary + gate results** — one line per phase: phase, gate (**PASS/FAIL/N-A/BLOCKED**, plus
   **SIMULATED** for a DRY-RUN Phase 6), human-equiv approver.
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

### Close-out — restore the tracked tree (DRY-RUN)

**DRY-RUN** — after writing the FINAL-REPORT, diff the current `git status --porcelain` against the
`logs/00-tree-baseline.txt` snapshot. **Restore the delta** — `git checkout -- <path>` for every
tracked file that was clean at baseline but is now dirty (e.g. `.secrets.baseline`, `uv.lock`
touched by `detect-secrets`/`uv run`), and remove new untracked artefacts written outside the
sandbox. Leave baseline-dirty files and the gitignored `reports/<SLUG>/` sandbox untouched. Report
the restored paths in the run header, then confirm the tracked tree matches the baseline.

**CODE** — do **not** restore: the working-tree changes ARE the deliverable, so reverting them
would destroy the work. Only verify the change set is the intended one and that any _incidental_
tooling churn (e.g. `.secrets.baseline` timestamp) is reconciled. Never run `git checkout`/`git
clean` over the implementation.

## Guardrails for the orchestrator itself

- One spec per invocation. **You** (the orchestrator) do not write product code yourself — in
  CODE mode the `phase-executor` subagent performs the implementation; you plan, brief, gate,
  and report. In DRY-RUN no `src/` is touched at all.
- Honour `CLAUDE.md §14` escalation triggers; if one fires, emit `[HITL-ESCALATE]` and stop —
  in **both** modes.
- Never push, merge, tag, release, deploy, or change a flag/autonomy setting without an
  explicit human approval in this session — regardless of mode.
- Respect the 2-skill budget per task (ADR-0060) when briefing the executor.
