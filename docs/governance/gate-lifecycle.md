# Governance Gate Enforcement Lifecycle — Burn-in Log

> **Status:** Active · **Governing ADR:** [ADR-0070](../adr/ADR-0070-governance-gate-enforcement-lifecycle.md) · **Owner:** Tech Lead + Security Lead

This is the **authoritative record** of every governance gate's transition from **report mode**
(`continue-on-error: true`) to **blocking**. ADR-0070 forbids a gate staying advisory
indefinitely: report-only is a _phase_, not a terminal state.

## Burn-in exit criterion (ADR-0070)

A report-mode gate may flip to blocking once it has accumulated:

- **≥ 15 consecutive PR runs** _OR_ **14 calendar days**, whichever comes first, **with**
- **zero false-positive failures** — a false positive **resets** the window.

The flip is an ISO 27001 **`normal-change`** ([ADR-0027](../adr/ADR-0027-iso27001-change-management.md))
and requires explicit **HITL approval**. The **day-zero property is preserved**: every gate must
still no-op gracefully on a fresh clone _before_ `make template-init` — blocking applies to
initialized repositories only.

Check progress at any time:

```bash
make burn-in-status                       # human-readable progress for the control-binding gate
python3 scripts/governance/burn_in_status.py --require-met   # exit 2 if NOT yet met (flip precondition)
```

## How a run gets recorded

The control-binding step in `ci.yml` runs report-mode on every PR and writes an **objective
verdict row** (PASS / FAIL, from its exit code) to the GitHub Actions **step summary**. A
maintainer copies that row into the table below and — **only for a FAIL** — classifies it as a
**false positive?** (`yes` = the gate flagged a PR that did _not_ actually need the declaration;
`no` = the gate correctly caught a real omission). PASS rows and correct-FAIL rows preserve the
streak; a `yes` row resets it.

---

## Gate registry

| Gate                                                  | Workflow / step                                         | Mode         | Burn-in                                                | Notes                                                             |
| ----------------------------------------------------- | ------------------------------------------------------- | ------------ | ------------------------------------------------------ | ----------------------------------------------------------------- |
| Control-binding (ADR-0061)                            | `ci.yml` → _Control-binding governance gate_            | **report**   | in progress (below)                                    | First gate through the ADR-0070 lifecycle                         |
| Staging DAST attestation (W2-T3)                      | `cd-production.yml` → _Verify staging DAST attestation_ | **report**   | in progress (below)                                    | Promotion gate; report-mode so it cannot brick prod deploys       |
| Change-type label / CAB (W1-2)                        | `pr-governance.yml` → _Change-type label (CAB)_         | **report**   | in progress (below)                                    | PR-time CAB; report-mode while the labeling convention is adopted |
| High-risk Action Guard (F7)                           | `pr-governance.yml` → _High-risk Action Guard (F7)_     | **blocking** | n/a (introduced blocking, deterministic 38/38 suite)   | W1-T3                                                             |
| Chaos Smoke (W2-10)                                   | `chaos-smoke.yml` → _Chaos Smoke (resilience)_          | **blocking** | n/a (deterministic; path-filtered to resilience paths) | Single-fault resilience smoke on PRs touching workers/hitl/retry  |
| Conventional PR title / Spec / Issue / Version        | `pr-governance.yml`                                     | **blocking** | past lifecycle                                         | Pre-existing                                                      |
| detect-secrets · Bandit · CodeQL · Trivy · ZAP (DAST) | `ci.yml` / `codeql.yml` / `secret-scanning.yml`         | **blocking** | past lifecycle (ADR-0070 §Neutral)                     | Pre-existing                                                      |

---

## Control-binding gate (ADR-0061) — burn-in log

<!-- BURN-IN-START: 2026-06-12 -->
<!-- BURN-IN-TARGET: control-binding-gate -->

Window restarts the day after any `yes` (false-positive) row. Placeholder rows (PR = `—`) are
ignored by `burn_in_status.py`.

| Date (UTC) | PR  | Verdict | False positive? | Notes                                                                             |
| ---------- | --- | ------- | --------------- | --------------------------------------------------------------------------------- |
| 2026-06-12 | —   | —       | —               | Burn-in started (ADR-0070, W1-T2). Awaiting first report-mode run on the next PR. |

### Exit evidence (fill on completion)

When `make burn-in-status` reports **MET**, record here before opening the flip PR:

- Window: `<start>` → `<end>` · Clean runs: `<n>` · Days: `<d>` · FP resets: `<k>`
- Criterion satisfied via: `runs>=15` | `days>=14`
- `burn_in_status.py --require-met` exit code: `0`
- Flip PR: `#<NNN>` · HITL approver: `<name>` · Change class: `normal-change`

### The flip (prepared, NOT yet applied)

Flipping to blocking is a **one-line** change to `.github/workflows/ci.yml` — **remove** the
`continue-on-error: true` line from the _Control-binding governance gate (ADR-0061)_ step. Do
**not** apply it until the burn-in above is MET and HITL-approved. The day-zero no-op
(placeholders before `make template-init`) is already handled inside
`scripts/governance/check_control_bindings.py` and must remain intact after the flip.

---

## Staging DAST attestation gate (W2-T3) — burn-in log

<!-- BURN-IN-START: 2026-06-12 -->
<!-- BURN-IN-TARGET: staging-dast-attestation -->

The `cd-production.yml` _Verify staging DAST attestation_ step runs in **report mode**: a missing
or invalid staging-DAST cosign attestation on the image digest warns but does not block promotion.
Record one row per production-promotion run (whether the attestation verified). A `yes` in
_False positive?_ (the attestation was present and valid but the step reported failure) resets the
window.

| Date (UTC) | PR/Run | Verdict | False positive? | Notes                                                                       |
| ---------- | ------ | ------- | --------------- | --------------------------------------------------------------------------- |
| 2026-06-12 | —      | —       | —               | Burn-in started (ADR-0070, W2-T3). Awaiting first production-promotion run. |

Check progress: `make burn-in-status GATE=staging-dast-attestation`.

### The flip (prepared, NOT yet applied)

Flip to blocking by **removing** `continue-on-error: true` from the _Verify staging DAST
attestation_ step in `.github/workflows/cd-production.yml`, after this burn-in is MET and
HITL-approved (`normal-change`). Until then a missing attestation cannot block a production deploy.

---

## Change-type label / CAB gate (W1-2) — burn-in log

<!-- BURN-IN-START: 2026-06-12 -->
<!-- BURN-IN-TARGET: change-type-label -->

The `pr-governance.yml` _Change-type label (CAB)_ step runs in **report mode**: a PR missing a
single `standard/normal/emergency-change` label (or `Refs: RFC-NNNN` for normal/emergency) warns
but does not block, while contributors adopt the labeling convention. Docs-only PRs and bots are
exempt. A `yes` in _False positive?_ (the PR legitimately needed no change-type, e.g. a release PR)
resets the window.

| Date (UTC) | PR  | Verdict | False positive? | Notes                                                                      |
| ---------- | --- | ------- | --------------- | -------------------------------------------------------------------------- |
| 2026-06-12 | —   | —       | —               | Burn-in started (ADR-0070, W1-2). Awaiting first PRs under the convention. |

Check progress: `make burn-in-status GATE=change-type-label`.

### The flip (prepared, NOT yet applied)

Flip to blocking by **removing** `continue-on-error: true` from the _Require exactly one change-type
label_ step in `.github/workflows/pr-governance.yml`, after this burn-in is MET and HITL-approved
(`normal-change`), then add **Change-type label (CAB)** to the required checks in
`.github/rulesets/main.json`.

---

## Waivers (ADR-0070 §4)

A gate may only remain report-only **past** its burn-in with a documented, time-boxed waiver.

| Gate     | Reason | Owner | Granted | Review by |
| -------- | ------ | ----- | ------- | --------- |
| _(none)_ |        |       |         |           |
