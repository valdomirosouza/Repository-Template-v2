# How-to: Deliver a spec with `/deliver`

> **Audience:** anyone driving a feature through the repo's lifecycle.
> **Prereqis:** an **approved** spec under `specs/` (no code without a spec — CLAUDE.md §2).
> **Skill source:** [`.claude/skills/deliver/SKILL.md`](../../.claude/skills/deliver/SKILL.md) ·
> **Lifecycle:** [`docs/process/WORKFLOW.md`](../process/WORKFLOW.md) (ADR-0058) ·
> **Tiers:** [`docs/process/gates/phase-gates.yaml`](../process/gates/phase-gates.yaml) (ADR-0064)

`/deliver` is a **thin orchestrator**: it drives **one** spec through the 15-phase Agentic
Spec-Driven Delivery lifecycle (Phase 0–14), delegating each phase to the `phase-executor`
subagent, and emits `reports/<slug>/FINAL-REPORT.md`. **Agents draft, analyze, test, recommend;
humans approve, own, operate** — the run **stops at every human gate** and never autonomously
pushes, merges, tags, releases, deploys, or changes a feature flag.

---

## Usage

```
/deliver [mode] [tier] [language] <path-to-spec.md>
```

All three leading tokens are **optional** and **classified by value** (not position), so order and
omission are tolerated. Defaults: **`dry-run` · `GOVERNED` · `PYTHON`**. The spec path is the token
ending in `.md` (or containing `/`); if it's missing, `/deliver` asks and stops — it never invents a
spec.

```
/deliver specs/privacy/redis-tls.md                      # dry-run · GOVERNED · PYTHON
/deliver code specs/security/rbac-model.md               # real impl, GOVERNED, PYTHON
/deliver code STANDARD specs/api/async-api-design.md     # real impl, STANDARD tier
/deliver dry-run TRIVIAL specs/k8s/probe-strategy.md     # quick simulation, TRIVIAL
/deliver code REGULATED java specs/foo.md                # full ceremony, Java stack
/deliver java code standard specs/foo.md                 # same as: code STANDARD java (order-free)
```

`/deliver` echoes the resolved axes before doing anything, e.g.
`Mode: CODE · Tier: STANDARD · Language: JAVA · Spec: specs/foo.md`.

---

## The three axes

### 1. `mode` — DRY-RUN vs CODE (default `dry-run`)

| Mode                    | What it does                                                                                                                        | Writes to                                                       | Human gates                                                                                            |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **`dry-run`** (default) | **Governed simulation** — drafts each phase's artefact and simulates every gated action                                             | `reports/<slug>/` **only** (never `src/`, `tests/`, `docs/`, …) | Auto-approved **and logged** (`HITL: auto-approved (dry-run)`); a CLAUDE.md §14 escalation still STOPs |
| **`code`**              | **Real implementation** — writes code/tests/ADRs/docs into the working tree (local, uncommitted) and runs the real validation suite | the real tree                                                   | **Real STOPs** — halts at every human gate and waits for you                                           |

**CODE-mode hard boundary (non-negotiable).** Even in CODE mode, `/deliver` implements and prepares
but **never** performs an outward-facing/irreversible action on its own. It STOPs and waits for your
explicit approval at: `git push`, opening/merging a PR, tagging/releasing (Phases 7/12/13); any
deploy/rollback/canary (Phases 12–13); any feature-flag/autonomy/ACL change (ADR-0015); and any
CLAUDE.md §14 trigger (e.g. touching `src/guardrails/` or `hitl_gateway.py`, >3 ADRs, coverage
<75%, a missing spec). DRY-RUN simulates-and-logs these; CODE STOPs on them.

### 2. `tier` — the scope axis (default `GOVERNED`, ADR-0064)

The tier **right-sizes which _process_ phases run** — the lifecycle dual of the 2-skill budget
(ADR-0060: _not every spec deserves every phase_). The authoritative tier → phase mapping lives in
[`phase-gates.yaml`](../process/gates/phase-gates.yaml) (`tiers:`, each phase's `applicability:`).

| Tier        | Intended scope                                                      | Runs                                                                                           |
| ----------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `TRIVIAL`   | localized, low-risk; no data/security/AI surface, no new dependency | control phases + a lightweight spec; process phases (Conception, Grooming, Post-Deploy) waived |
| `STANDARD`  | a normal feature/fix in one module                                  | a normal path; heavier process phases run conditionally                                        |
| `GOVERNED`  | **default** — cross-cutting / production-shipping change            | the full lifecycle                                                                             |
| `REGULATED` | a control surface (guardrails, autonomy, PII/financial core)        | every phase, no waivers                                                                        |

Two rules keep this safe:

- **Control phases are never waived** — Testing (8), Security & DevSecOps (9), AI Safety (10, when
  it applies), Code Review (7), Discovery PII classification (2), Production CAB (13), and the
  _no-code-without-a-spec_ invariant (4) run in **every** tier (`applicability.control_phase: true`).
  Right-sizing trims **process** ceremony only.
- **An auto-escalation safety valve** self-corrects under-sizing: if a run exceeds its declared tier
  mid-flight — a file/ADR/module **scope ceiling**, a **coverage drop**, a **new dependency**, an
  **unanticipated control trigger** (`.github/control-triggers.yml`), a **>5-step task expansion**,
  or a **guardrail touch** — `/deliver` **promotes to the next tier**, **re-enters** the skipped
  phases, and emits a `TIER_ESCALATION` line in the FINAL-REPORT. Escalation is one-way (promotion
  only) and auditable.

Omitting the tier defaults to `GOVERNED`, so a forgotten tier never _under_-governs.

### 3. `language` — the stack (default `PYTHON`)

Selects **where** code lands and **which** validation targets run for evidence. It does **not**
change any gate, guardrail, or human-stop — those are language-agnostic.

| `language`                | CODE writes to                   | Evidence (`make`) targets                                                  |
| ------------------------- | -------------------------------- | -------------------------------------------------------------------------- |
| `PYTHON` (default)        | `src/` + `tests/`                | `make lint-python` · `make test-unit-python` · `make test-security-python` |
| `JAVA`                    | `services/<name>/` (Spring Boot) | `make lint-java SERVICE=<name>` · `make test-unit-java SERVICE=<name>`     |
| `GO`                      | `services/<name>/`               | `make lint-go SERVICE=<name>` · `make test-unit-go SERVICE=<name>`         |
| `NODE` / `TYPESCRIPT`     | `frontend/<app>/` (Next.js)      | `make lint-frontend APP=<app>` · `make test-unit-frontend APP=<app>`       |
| `IAC` (Terraform/Ansible) | `infrastructure/`                | `terraform fmt -check` + `terraform validate` + Checkov, or `ansible-lint` |
| _other_                   | the stack's conventional layout  | the stack's standard lint + unit (gap logged if no repo target exists)     |

Cross-cutting gates (DevSecOps SAST/SCA/SBOM, AI-safety, OTel, privacy/PII, coverage ≥ 80%, and
every human gate) apply regardless of language.

---

## What you get

`/deliver` always begins at **Phase 0**: it writes `reports/<slug>/00-plan.md` (resolved
mode/tier/language, the 15-phase plan with each phase's `required`/`conditional`/`waivable` status
for the tier, governing ADRs, guardrails, the human-gate list) and `reports/<slug>/backlog.yaml`,
then **STOPs at a plan-approval gate** before executing any phase (DRY-RUN auto-approves-and-logs;
CODE waits for you).

After the phases run it writes `reports/<slug>/FINAL-REPORT.md`:

0. **Run header** — mode, tier (+ effective tier if the safety valve escalated), language, spec, and
   the human gates the run stopped at.
1. **Summary + gate results** — one line per phase: `PASS` / `FAIL` / `N-A` / `BLOCKED` / `WAIVED`
   (+ `SIMULATED` for a DRY-RUN Phase 6), plus every `TIER_ESCALATION`.
2. **Requirement-traceability table** — one row per acceptance criterion (`§12` of your spec).
3. **Task/sub-task table** — agent wall-clock vs human-equivalent estimate, with a speedup ratio.
4. **Evidence appendix** — validation-log excerpts.
5. **Open-HITL-items list** — every gate that needs a real human, with its payload.

> A well-filled **§12 Acceptance Criteria** is what gives `/deliver` real material to validate —
> each criterion becomes a row in the traceability table. See
> [`skills/sdlc/spec-lifecycle.md`](../../skills/sdlc/spec-lifecycle.md) and
> [`specs/SPEC-TEMPLATE.md`](../../specs/SPEC-TEMPLATE.md).

---

## Picking mode + tier

| Situation                                               | Suggested invocation                                         |
| ------------------------------------------------------- | ------------------------------------------------------------ |
| First look — see the governed plan with no side-effects | `/deliver specs/<…>.md` (dry-run · GOVERNED)                 |
| Quick, localized change (config tweak, ≤ 3 files)       | `/deliver dry-run TRIVIAL specs/<…>.md`, then `code TRIVIAL` |
| A normal feature in one module                          | `/deliver code STANDARD specs/<…>.md`                        |
| Cross-cutting / ships to production                     | `/deliver code specs/<…>.md` (GOVERNED)                      |
| Touches guardrails / autonomy / PII core                | `/deliver code REGULATED specs/<…>.md`                       |
| Non-Python stack                                        | add the language, e.g. `/deliver code java specs/<…>.md`     |

Unsure of the tier? Leave it off — `GOVERNED` is the safe default, and the safety valve promotes it
if the change turns out bigger than declared.

---

## Guardrails (both modes)

- **One spec per invocation**; honour the 2-skill budget per task (ADR-0060).
- **Never** autonomously push, merge, tag, release, deploy, roll back, or change a flag/ACL/autonomy
  setting — these always require an explicit human gate (CLAUDE.md §3/§14; ADR-0011/0015/0034).
- DRY-RUN keeps all artefacts under `reports/<slug>/` and restores any incidental tracked-file churn;
  CODE leaves the implementation **uncommitted** in the working tree for your review.

## See also

- [`docs/process/WORKFLOW.md`](../process/WORKFLOW.md) — the 15-phase lifecycle (human-readable)
- [`docs/process/gates/phase-gates.yaml`](../process/gates/phase-gates.yaml) — authoritative phase
  gates + tiers + escalation triggers
- [`docs/sdlc/agentic-spec-driven-delivery.md`](../sdlc/agentic-spec-driven-delivery.md) — the
  canonical delivery model
- [`docs/quickstart/hybrid-workflow.md`](hybrid-workflow.md) — Vibe ↔ Agentic blended workflow
- [`docs/sdlc/agent-handoff-schema.md`](../sdlc/agent-handoff-schema.md) — the sub-agent
  receive/return contract `/deliver` uses
