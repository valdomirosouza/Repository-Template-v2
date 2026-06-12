# ADR-0070 — Governance Gate Enforcement Lifecycle (report-mode → blocking-mode)

**Status:** Accepted
**Date:** 2026-06-12
**Authors:** Valdomiro Souza
**Milestone:** v2.16.0 — Governance Enforcement Hardening (Track A)
**Relates to:** [ADR-0061](ADR-0061-control-binding-ci-gate.md) (control-binding CI gate), [ADR-0064](ADR-0064-delivery-right-sizing-tiers.md) (tiers), [ADR-0071](ADR-0071-repository-settings-as-code.md) (settings-as-code)

---

## Context

The repository's biggest weakness — reached independently by an external OWASP/agentic review
(`improvements-2026-06-12-2021.md`) and a 4-agent internal scan (`reports/STRENGTHENING-PLAN.md`)
— is the gap between **documented** governance and **enforced** governance. Concretely:

- The control-binding governance gate runs with `continue-on-error: true` (report-only) — it
  reports declaration-discipline violations but does not block.
- Java lint/SAST/coverage gates were authored but silently un-enforced for months (a make-target
  reactor bug + execution-scoped jacoco rules), surfaced only this week.

Gates are introduced report-only **for good reason** — a brand-new gate with a high false-positive
rate that blocks on day one erodes trust and gets disabled. But report-only must be a **phase**,
not a terminal state, or "we have a gate" becomes theatre. There is currently no policy defining
when a gate must graduate from report-mode to blocking.

## Decision

Every governance gate has an explicit, auditable **lifecycle**:

1. **Introduced in report mode** (`continue-on-error: true`) with a **defined burn-in exit
   criterion**.
2. **Burn-in exit criterion:** ≥ **15 consecutive PR runs** OR **14 calendar days**, whichever
   comes first, with **zero false-positive failures** (a false positive resets the count).
3. **Flip to blocking** is a `normal-change` (ISO 27001 / ADR-0027) requiring explicit **HITL
   approval**; the burn-in evidence is recorded in `docs/governance/gate-lifecycle.md`.
4. A gate **may not remain report-only past its burn-in** without a **documented waiver** (owner,
   reason, review date) in the same log.
5. The **day-zero / template property is preserved**: a gate must still no-op gracefully on a
   fresh clone _before_ `make template-init` (placeholders are intentional) — blocking applies to
   initialized repositories only.

This ADR governs _every_ gate's transition, starting with flipping the control-binding gate to
blocking once its burn-in is evidenced.

## Consequences

### Positive

- Report-only stops being a place gates go to die; "we have a gate" becomes "the gate blocks".
- The burn-in window keeps the safest path the easiest path (no day-one false-positive blocking).
- The waiver mechanism makes any _intentional_ non-enforcement explicit and time-boxed.

### Negative / Trade-offs

- A small ceremony per gate (burn-in tracking + a flip PR). Acceptable — it is the price of
  enforceable governance.
- The 15-run / 14-day threshold is a heuristic; a noisy gate may need its false-positives fixed
  before it can graduate (which is the point).

### Neutral

- Existing blocking gates (Bandit, detect-secrets, ZAP, Trivy, conventional-title) are already
  past this lifecycle; the policy formalises the path for new and report-only ones.

## Alternatives Considered

- **Flip everything to blocking immediately** — rejected: day-one false positives erode trust and
  invite `continue-on-error` or `--no-verify` bypasses, the opposite of the goal.
- **Leave report-only at author's discretion** — rejected: that is the current state, and it is
  how the control-binding gate stayed advisory indefinitely.

## References

- `reports/STRENGTHENING-PLAN.md` W3-2 · `improvements-2026-06-12-2021.md` §1 / backlog P0
- `governance-enforcement-hardening-v1.0.0.md` §1 (ADR-0066-as-proposed → renumbered 0070)
- [ADR-0061](ADR-0061-control-binding-ci-gate.md) · [ADR-0027](ADR-0027-iso27001-change-management.md)
