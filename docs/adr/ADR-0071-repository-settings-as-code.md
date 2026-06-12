# ADR-0071 — Repository Settings as Code (branch protection codified + drift-checked)

**Status:** Accepted
**Date:** 2026-06-12
**Authors:** Valdomiro Souza
**Milestone:** v2.16.0 — Governance Enforcement Hardening (Track A — keystone)
**Relates to:** [ADR-0070](ADR-0070-governance-gate-enforcement-lifecycle.md) (gate lifecycle), [ADR-0061](ADR-0061-control-binding-ci-gate.md) (control-binding gate), [ADR-0064](ADR-0064-delivery-right-sizing-tiers.md) (tiers / applicability)

---

## Context

A CI job that exists in the repo is **not** the same as a CI job that is enforced. GitHub branch
protection / rulesets decide which checks are _required_ to merge — and those settings live in the
**repository UI**, outside version control. This is the root cause behind a recurring failure this
week: Java lint, SAST, and coverage jobs existed in `ci-java.yml` but were never required, so a
PR could merge with them red (and several were silently broken for months without anyone noticing,
precisely because nothing required them).

A blocking gate that is not a _required check_ is still bypassable by an admin merge or by editing
the workflow. **UI-only branch protection is therefore a governance bypass** — the settings that
decide what "enforced" means are themselves un-versioned, un-reviewed, and un-audited.

This is the **keystone** of the enforcement-hardening milestone: making gates blocking (ADR-0070)
has no teeth unless the "which checks are required" decision is itself codified and drift-checked.

## Decision

**Branch protection / rulesets are governance configuration and must be versioned in-repo.**

1. **Versioned rulesets:** the required-check set and protection rules for `main` (and `develop`)
   live in `.github/rulesets/*.json` — the single source of truth.
2. **Bootstrap script:** `scripts/governance/apply_branch_protection.sh` applies the versioned
   rulesets via `gh api`. Applying it requires **admin scope and is a human action** — an agent
   prepares the JSON + script but **never** modifies access controls itself (CLAUDE.md §14;
   ADR-0015 sibling-class change).
3. **Drift-audit:** a scheduled `branch-protection-audit.yml` workflow compares live settings to
   the versioned source and **fails on drift** — UI-only changes are caught, not silently
   tolerated.
4. **Applicability-driven required set:** which language CIs are required is driven by the
   control-applicability matrix (ADR-0064 / ADR-0061), so a template consumer _without_ Java/Go is
   **not** blocked on day zero. The day-zero / pre-`template-init` property is preserved.
5. **Required-check set encoded** (subject to applicability): `governance` (control-binding),
   the per-language CIs (`python`/`java`/`go`/`frontend`), `test-security`, `dast-baseline`,
   `trivy`, `sbom`, `contract-drift`, AI-safety/model-contract where applicable, and
   `verify-f7-hook` (the high-risk-guard regression suite).

## Consequences

### Positive

- The set of enforced gates becomes versioned, reviewable, and PR-gated — the same rigor applied
  to code now applies to the rules that decide what "enforced" means.
- Drift-audit makes any out-of-band UI change visible within a scheduled cycle.
- Directly closes the "Java gates were never required" root cause and makes ADR-0070's blocking
  flips actually binding.

### Negative / Trade-offs

- Bootstrap/apply is a **human admin step** — the agent cannot self-apply (by design; this is a
  containment boundary, not a limitation to work around).
- Ruleset JSON must be kept current with new workflows; the drift-audit surfaces staleness.

### Neutral

- Adopters fork the rulesets and apply them with their own admin credentials as part of
  `template-init` onboarding.

## Alternatives Considered

- **Keep branch protection in the UI** — rejected: un-versioned, un-audited, the current bypass.
- **A GitHub App / Terraform GitHub provider** — heavier; deferred. `gh api` + JSON + a drift
  workflow is the lowest-friction codification and needs no extra infra for a template.

## References

- `improvements-2026-06-12-2021.md` backlog P0 #2 · `reports/STRENGTHENING-PLAN.md` W2-4
- `governance-enforcement-hardening-v1.0.0.md` §1/§2 W1-T1 (ADR-0067-as-proposed → renumbered 0071)
- [ADR-0070](ADR-0070-governance-gate-enforcement-lifecycle.md) · [ADR-0061](ADR-0061-control-binding-ci-gate.md)
