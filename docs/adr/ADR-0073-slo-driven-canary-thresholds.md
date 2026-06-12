# ADR-0073 — SLO-Driven Canary Thresholds (service-level config, no hard-coded gates)

**Status:** Accepted
**Date:** 2026-06-12
**Authors:** Valdomiro Souza
**Milestone:** v2.16.0 — Governance Enforcement Hardening (Track B)
**Relates to:** [ADR-0028](ADR-0028-dora-metrics.md) (DORA), [ADR-0027](ADR-0027-iso27001-change-management.md) (change management / canary), [ADR-0071](ADR-0071-repository-settings-as-code.md) (config-as-code)

---

## Context

The production workflow runs strong canary gates using Golden Signals — error rate and p99 latency
are checked at the 5% and 25% rollout steps, which is exactly the right operational pattern. But
the thresholds are **hard-coded in the workflow YAML** (e.g. `error_rate > 0.01`, `p99 > 0.5`).

A single set of numbers baked into the pipeline cannot be right for every service: a batch worker
and a latency-critical API have different acceptable error rates and p99s. Hard-coded thresholds
also live outside the SLO documents that are supposed to be the single source of truth for service
objectives (`docs/sre/slo/`), so the gate and the SLO can silently disagree.

## Decision

**Canary / error-budget thresholds live in per-service SLO configuration; workflows read them at
runtime. Hard-coded numeric thresholds in workflow YAML are prohibited.**

1. **Per-service SLO files:** `docs/sre/slo/<service>.yaml` (schema included) define the canary
   thresholds (error-rate, p99) and the error-budget policy for each service.
2. **Workflow reads at runtime:** the production canary workflow resolves thresholds from the
   service's SLO file (e.g. via `yq`) at the 5% / 25% steps — no literals in the YAML.
3. **Error-budget gate:** promotion is **blocked if remaining error budget ≤ 10%** (a burn-aware
   gate, not just a point-in-time threshold).
4. **No silent defaults:** a deployed service **without** an SLO file **fails the pipeline** —
   missing SLO is a configuration error, not a fall-through to a baked-in number.
5. **Lint-enforced:** a check fails CI if numeric error-rate/p99 thresholds appear in workflow YAML
   (anti-regression).

## Consequences

### Positive

- Thresholds become service-appropriate and live next to the SLO they derive from — one source of
  truth, owned by SRE.
- The error-budget gate ties promotion to the documented reliability policy, not an arbitrary
  instantaneous number.
- "No SLO ⇒ pipeline fails" prevents a new service from silently inheriting another's thresholds.

### Negative / Trade-offs

- Every deployed service now must ship an SLO file — a small upfront cost that is the correct SRE
  discipline anyway (it is already a PRR expectation).

### Neutral

- The golden-signals service's existing `slo.yaml` (SPEC-LGS-001) becomes the worked example of
  the schema.

## Alternatives Considered

- **Keep hard-coded thresholds** — rejected: one-size-fits-all, and divorced from the SLO docs.
- **Global default + per-service override** — rejected: a global default is exactly the silent
  fall-through this ADR removes; explicit-or-fail is safer.

## References

- `improvements-2026-06-12-2021.md` backlog P1 #7 · `reports/STRENGTHENING-PLAN.md` (Observability)
- `governance-enforcement-hardening-v1.0.0.md` W2-T4 (ADR-0069-as-proposed → renumbered 0073)
- [ADR-0028](ADR-0028-dora-metrics.md) · `docs/sre/slo/`
