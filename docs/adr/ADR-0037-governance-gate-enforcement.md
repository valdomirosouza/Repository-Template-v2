# ADR-0037: Governance Gate CI Enforcement

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Issue:** #14
**Related ADRs:** ADR-0011 (HITL/HOTL Model), ADR-0015 (Feature Flag Strategy), ADR-0034 (Agentic Escalation Protocol)

---

## Context

The cross-functional governance council (COO, CFO, CISO, AI Governance Lead, General Counsel)
is documented in `docs/governance/` RACI and ADR-0015, but its approval has no machine-
enforceable enforcement in CI. A PR that enables `autonomous-mode-full` or modifies
`hitl_gateway.py` can be merged with only standard code-review approval, bypassing the
council entirely.

Gartner's Enterprise Governance component specifically identifies this as a root cause of
the 40% agentic AI project cancellation rate: governance councils exist on paper but are
not wired into the deployment pipeline.

Gap G3 from the Gartner Agentic AI Compliance gap analysis (2026-06-05).

---

## Decision

Introduce a blocking CI workflow (`governance-gate.yml`) that:

1. Triggers on pull requests targeting `main` that touch any of:
   - `infrastructure/feature-flags/flags/autonomous-mode*.yaml`
   - `infrastructure/feature-flags/flags/autonomy-tier-ready.yaml`
   - `src/agents/hitl_gateway.py`

2. Checks for the presence of **both** governance labels:
   - `governance-council-approved` — applied by COO or CISO after council review
   - `legal-reviewed` — applied by General Counsel after compliance review

3. Fails with a descriptive message listing which labels are missing and the approval
   process to follow (see `docs/governance/governance-labels.md`).

Additionally, add a `harness/business-value-check.yml` informational gate that verifies
every agent PR answers the six mandatory Business Value questions in `skills/sre/prr.md`.

---

## Consequences

**Positive:**

- Council approval is now machine-enforced, not just advisory
- Governance label history provides an immutable audit trail of who approved what and when
- Reduces risk of ungoverned autonomy escalation reaching production

**Negative:**

- Adds a process step to the merge path for autonomy-affecting changes
- Emergency changes require an out-of-band council session (mitigated by the async approval
  option documented in `governance-labels.md`)

**Neutral:**

- Label application is manual (by designated approvers only); the gate only checks presence
- Non-production flag metadata changes run the gate in informational mode (non-blocking)

---

## Alternatives Considered

- **CODEOWNERS only:** GitHub CODEOWNERS can require specific reviewer approval but cannot
  distinguish label-based sign-off from a governance council vs. a regular code reviewer.
  Rejected — insufficient auditability.

- **External approval API:** Integrate with a GRC tool (ServiceNow, Jira) to check ticket
  approval status. Accepted as a future enhancement; the label approach is simpler and
  requires no external dependency.
