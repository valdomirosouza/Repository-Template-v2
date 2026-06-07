# ADR-0061 — Control-binding obligations enforced as a CI governance gate

**Status:** Accepted
**Date:** 2026-06-07
**Authors:** Valdomiro Souza

---

## Context

ADR-0060 adopted the Task Atomicity & 2-Skill Budget directive and
`docs/governance/control-applicability-matrix.md` enumerated the cross-cutting
compliance/privacy/security control-binding triggers. Both are **advisory**: whether a
change honours an obligation depends on the agent _remembering_ to bind the matching control
under its `## Skills — load before executing` block. Nothing enforces it — a PR can modify
`src/guardrails/pii_filter.py` and never declare `privacy/pii`.

RFC-0004 proposes closing that loop in CI. This ADR records the decision.

## Decision

Enforce control-binding **declaration discipline** as a CI governance gate, wired into the
existing `Governance Checks` job of `.github/workflows/ci.yml`:

1. A deterministic, offline checker (`scripts/governance/check_control_bindings.py`) reads
   the PR's changed files + diff, the declared bindings (parsed from the PR body's
   `## Skills — load before executing` block), and two config files:
   `.github/control-triggers.yml` (the canonical trigger ruleset) and
   `docs/governance/applicability-matrix.yml` (conditionality config).
2. For every trigger whose path globs (and optional diff-content regexes) match, the required
   controls must be declared. Missing control ⇒ the PR fails.
3. The **2-skill budget** is enforced (max 2 _skill_ controls; ambient ADR controls do not
   count). A **3-domain atomicity smell** fails the PR (overridable with an `atomic-exception`
   label, logged).
4. **Conditional** controls (e.g. SOX / ADR-0026) are required only when the applicability
   matrix marks them in scope; otherwise the checker emits an `EXEMPT` line, not a failure.
5. An inline allow-marker (`# control-binding: ignore <trigger-id> reason=...`) can suppress a
   single trigger on a single hunk; every suppression is logged. No blanket ignore.

The `applicability-matrix.yml` is the **machine-readable companion** to the human
`control-applicability-matrix.md` (ADR-0060), cross-linked, not a duplicate.

### Scope — what this gate is and is not

- **It enforces declaration discipline** — did the task bind the control? — _not_ the
  correctness of the control's implementation. A PR can declare `privacy/pii` and still
  mishandle PII; this gate does not catch that. Semantic compliance analysis is a non-goal.
- **It complements, not replaces, the scanners.** SAST/SCA/secret/DAST gates remain
  authoritative for their domains; this gate references the SBOM/SCA pipeline via the
  `sbom-sca-gate` ambient control.

## Consequences

**Positive**

- ADR-0060's control bindings become enforced, not merely remembered.
- The 2-skill budget and atomicity smell get a mechanical backstop, reinforcing decomposition.
- Conditionality is explicit and auditable (exemptions are printed, suppressions logged).

**Negative / costs**

- A new checker + config to maintain; possible false positives (mitigated by the allow-marker
  and a one-cycle report-mode rollout before blocking).
- More declaration ceremony on PRs; over-budget/atomicity smells force splits — intended, but
  real friction.

**Neutral**

- No existing gate is weakened or reordered; the new step is additive in `Governance Checks`.

## Alternatives

See RFC-0004 §3 (keep relying on agent memory; full semantic compliance analysis;
pre-commit-only). All rejected in favour of an additive, deterministic CI gate.

## Corrections vs the source prompt

The source prompt (`ci-control-binding-gate-prompt-v1.0.0.md`) targeted an earlier repo
state. This decision uses **ADR-0061** (the prompt's "ADR-0031" already exists); the
implementation declares real skills (`devsecops/pipeline-security` +
`engineering/testing-strategy`); and the `llm-io` trigger binds the existing
`devsecops/owasp-top10` (no separate `owasp-llm-top10` skill exists).

## References

- RFC-0004 (proposal) · ADR-0060 (Task Atomicity & 2-Skill Budget)
- `docs/governance/control-applicability-matrix.md` (human matrix) · `docs/governance/applicability-matrix.yml` (machine config)
- ADR-0026 (SOX), ADR-0027 (ISO 27001), ADR-0029 (DevSecOps pipeline) — ambient controls
