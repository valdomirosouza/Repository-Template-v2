# ADR-0064 — Delivery Right-Sizing / Phase Applicability Tiers + Auto-Escalation Safety Valve

**Status:** Accepted
**Date:** 2026-06-09
**Authors:** Valdomiro Souza

---

## Context

`/deliver` (ADR-0058; `.claude/skills/deliver/SKILL.md`) traverses **all 15 phases (0–14)**
of the Agentic Spec-Driven Delivery lifecycle for every spec, regardless of scope. It has a
_mode_ axis (DRY-RUN | CODE) and a _language_ axis, but **no scope axis**. A one-file
`redis-tls` config tweak therefore produces the same 15 governed artifacts as a new bounded
context — most of them near-empty ceremony. The cost is agent time, context budget, and
reviewer fatigue, which erodes trust in the gates that _do_ matter. **Proportionality is itself
a governance property: gates are most credible when they are not theatre.**

This is the missing dual of two decisions we already made:

- **ADR-0060** (2-skill budget) decided that _not every task deserves every skill_ — and made
  that budget a decomposition oracle, not a mere ceiling.
- **ADR-0061** (control-binding CI gate) decided that obligations attach to a change by
  _what it touches_, conditionally, via an applicability matrix.

Right-sizing applies the same idea to the lifecycle: _not every spec deserves every phase_.
The risk is obvious and must be designed out: a scope classifier is a way to **under-govern by
mistake**. So tiering is only safe when paired with a **safety valve** — if a skipped phase
turns out to have been wrongly skipped, the run must self-correct, re-enter the phase, and
record that it did so. This mirrors the self-correcting escalation we already run in
`CLAUDE.md §14` (which already stops on ">3 ADRs" and "coverage <75%"); "scope exceeds the
declared tier" is a natural sibling trigger.

Source: `spec-driven-insights-for-repository-template-v2.md` §2.1, §2.2 (insights derived from
Spec-Driven v2.0.0 by Felipe Rodrigues, Tech Lead's Club, CC-BY-4.0).

## Decision

Give delivery a **scope axis** of four **tiers** and, per tier, declare which of the 15 phases
are `required`, `conditional`, or `waivable`. The mapping lives in
`docs/process/gates/phase-gates.yaml` as a per-phase `applicability:` block plus a top-level
`tiers:` and `escalation_triggers:` section — keeping `phase-gates.yaml` the single source of
truth — and is surfaced in `docs/governance/applicability-matrix.yml`.

### 1. Tiers

| Tier        | Intended scope                                                                                  | Scope ceiling (soft)             |
| ----------- | ----------------------------------------------------------------------------------------------- | -------------------------------- |
| `TRIVIAL`   | Localized, low-risk change; no data/security/AI surface, no new dependency (e.g. config tweak)  | ≤ 3 files, 0 ADRs, 1 module      |
| `STANDARD`  | A normal feature or fix contained within one module/bounded context                             | ≤ 10 files, ≤ 1 ADR, ≤ 2 modules |
| `GOVERNED`  | Cross-cutting change, new architectural decision, or anything that ships to production          | ≤ 25 files, ≤ 3 ADRs             |
| `REGULATED` | Touches a control surface that demands full ceremony (guardrails, autonomy, financial/PII core) | no ceiling — full lifecycle      |

**Default tier is `GOVERNED`** so omission never _under_-governs (conservative-by-default,
consistent with the default-deny posture of `phase-gates.yaml` and `applicability-matrix.yml`).

### 2. Per-phase applicability vocabulary

Each phase declares, per tier, one of:

- **`required`** — the phase gate must pass; its artifact is mandatory.
- **`conditional`** — required only when a named `condition` holds (e.g. `ai_or_agent_change`,
  `architectural_decision`, `processes_data`, `new_failure_mode`, `ships_release`,
  `deploys_prod`); otherwise recorded `N/A` and skipped.
- **`waivable`** — the phase's _process_ artifact may be down-scoped or skipped, but **only**
  with a recorded `PHASE_WAIVED: phase=<n> tier=<tier> reason=<…>` evidence line. The phase's
  embedded _controls_, if any, still apply.

### 3. The non-negotiable control floor (every tier)

**Right-sizing trims _process_ phases only — never _control_ phases.** The following are
`required` (or `conditional` on their own control trigger) in **every** tier and are **never
`waivable`**:

- **Phase 8 Testing** — coverage ≥ 80% + security/abuse-case tests (`CLAUDE.md §3.5`).
- **Phase 9 Security & DevSecOps** — SAST/SCA/secret/SBOM (`CLAUDE.md §3.2`, ADR-0029).
- **Phase 10 AI Safety** — `conditional` on `ai_or_agent_change` in _all_ tiers; when it fires
  it is mandatory and never waived (`CLAUDE.md §3.3`, ADR-0050/0051/0053).
- **Phase 7 Code Review** — ≥ 1 human approval (human oversight is a control, ADR-0011).
- **The PII/security classification carried in Phase 2 Discovery** — `conditional` on
  `processes_data`; mandatory whenever the change reads/stores/transmits personal data
  (ADR-0012, `CLAUDE.md §3.1`).
- **The spec-reference invariant in Phase 4** — _no code without a spec_ (`CLAUDE.md §3.4`)
  holds in all tiers. TRIVIAL may use a _lightweight_ spec form (issue + inline acceptance
  criteria) instead of a full `feature-spec.md`, but never _zero_ spec. Phase 4 is therefore
  `required` in every tier; only its **artifact weight** scales.

The resulting tier → phase matrix (`R` required · `C` conditional · `W` waivable):

| Phase                          | TRIVIAL | STANDARD | GOVERNED | REGULATED |
| ------------------------------ | :-----: | :------: | :------: | :-------: |
| 0 Intake                       |    R    |    R     |    R     |     R     |
| 1 Conception                   |    W    |    C     |    R     |     R     |
| 2 Discovery (NFR/PII)          |    C    |    C     |    R     |     R     |
| 3 Grooming                     |    W    |    C     |    R     |     R     |
| 4 Specification                |    R    |    R     |    R     |     R     |
| 5 Architecture                 |    C    |    C     |    C     |     R     |
| 6 Development                  |    R    |    R     |    R     |     R     |
| 7 Code Review _(control)_      |    R    |    R     |    R     |     R     |
| 8 Testing _(control)_          |    R    |    R     |    R     |     R     |
| 9 Security & DevSecOps _(ctl)_ |    R    |    R     |    R     |     R     |
| 10 AI Safety _(control, cond)_ |    C    |    C     |    C     |     C     |
| 11 Observability               |    C    |    C     |    R     |     R     |
| 12 Release Candidate           |    C    |    C     |    R     |     R     |
| 13 Production Deployment       |    C    |    C     |    C     |     R     |
| 14 Post-Deploy & Learn         |    W    |    C     |    R     |     R     |

### 4. The safety valve — auto-escalation

Each lower tier declares thresholds that, if exceeded mid-run, **force promotion to the next
tier**, re-entry of the now-required phases that were skipped, and emission of a
`TIER_ESCALATION` evidence line in the `/deliver` FINAL-REPORT (analogous to the existing
`HITL: auto-approved (dry-run)` evidence lines). Triggers (enumerated in
`phase-gates.yaml › escalation_triggers`):

- **file/module/ADR count** exceeds the declared tier ceiling;
- **coverage** would drop below 80% (and the `CLAUDE.md §14` hard stop at < 75% still fires);
- a **new dependency** is added (ties to the `dependency-or-pipeline` control trigger, ADR-0061);
- a **control trigger** in `.github/control-triggers.yml` fires that the tier did not anticipate
  (e.g. `personal-data`, `llm-io`, `deploy-change-process`) → escalate to at least `GOVERNED`;
- **inline task expansion reveals > 5 atomic steps** or complex dependencies → re-enter Phase 3
  Grooming and write a formal task breakdown (Spec-Driven's exact "wrongly-skipped" rule);
- the change **touches `src/guardrails/` or `src/agents/hitl_gateway.py`** → `REGULATED` +
  the `CLAUDE.md §14` dual-approval STOP.

Escalation is **one-way (promotion only)** and re-entrant: an escalated run never silently
drops a phase it has re-acquired. The `TIER_ESCALATION` line records
`from`, `to`, `trigger`, and `reentered_phases`.

## Consequences

### Positive

- `/deliver` stops running 15 phases of empty ceremony for a config tweak; agent time, context,
  and reviewer attention are spent in proportion to risk.
- The control floor is explicit and machine-checkable: trimming can only ever remove _process_
  ceremony, never a safety/privacy/security/AI-guardrail gate.
- Mis-classification self-heals via the safety valve, so tiering cannot quietly under-govern.
- Completes the proportionality story already begun by ADR-0060 (skills) and ADR-0061 (controls).

### Negative / Trade-offs

- A new dimension to maintain: every new phase must declare its `applicability` block, and the
  escalation thresholds need occasional tuning.
- A wrong (too-low) manual tier declaration shifts load onto the safety valve; if a trigger is
  mis-specified, a change could run under-governed until a downstream control catches it. The
  conservative `GOVERNED` default and the control-trigger escalation are the mitigations.

### Neutral

- No phase gate, guardrail, approval, or SDD invariant is weakened or removed; this ADR only
  declares _when a process phase may be down-scoped_, never _whether a control may be skipped_.
- `phase-gates.yaml` remains the single source of truth; `WORKFLOW.md` and
  `applicability-matrix.yml` are kept in sync with it.

## Alternatives Considered

1. **Keep the flat 15-phase traversal.** Rejected: it is the status quo whose cost (ceremony
   theatre, reviewer fatigue) motivated this ADR.
2. **A risk-class field on the spec instead of a delivery tier.** Rejected: risk class (Phase 0)
   already exists and answers a _different_ question ("how dangerous?"); the tier answers "how
   much _process_ does this scope warrant?". They compose — a `small-fix` risk class maps to
   `TRIVIAL`/`STANDARD`, an `AI`/`security` risk class forces `REGULATED`.
3. **Auto-classify with no manual override.** Rejected for v1: a classifier good enough to be
   _sole_ arbiter is out of scope; instead a human declares the tier (default `GOVERNED`) and the
   safety valve catches under-declaration. Full auto-classification can be a later ADR.
4. **Tiering without a safety valve.** Rejected outright: that is precisely the "under-govern by
   mistake" failure mode. §4 ships in this same ADR so right-sizing never lands without its net.

## References

- `spec-driven-insights-for-repository-template-v2.md` §2.1, §2.2 (source insight; CC-BY-4.0,
  Felipe Rodrigues / Tech Lead's Club)
- ADR-0058 (Agentic Spec-Driven Delivery workflow) · ADR-0052 (E2E workflow)
- ADR-0060 (Task Atomicity & 2-Skill Budget — the skills dual) · ADR-0061 (control-binding CI gate)
- ADR-0011 (HITL/HOTL oversight) · ADR-0034 (agentic escalation protocol) · ADR-0015 (feature flags)
- `CLAUDE.md` §3 (inviolable rules), §14 (escalation) · `docs/process/gates/phase-gates.yaml`
- `docs/process/WORKFLOW.md` · `.claude/skills/deliver/SKILL.md`
