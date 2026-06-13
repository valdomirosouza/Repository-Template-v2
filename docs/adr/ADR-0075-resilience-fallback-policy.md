# ADR-0075 — Resilience Fallback Policy (degrade-open vs fail-closed)

**Status:** Accepted
**Date:** 2026-06-13
**Authors:** Valdomiro Souza
**Relates to:** [ADR-0011](ADR-0011-hitl-hotl-decision.md) (HITL/HOTL), [ADR-0018](ADR-0018-encryption-at-rest.md) (encryption at rest), [ADR-0028](ADR-0028-dora-metrics.md) (DORA / MTTR)

---

## Context

The template's headline resilience pattern is the **in-memory fallback**: every infrastructure
dependency has an in-process substitute so the app starts and serves cleanly without a full stack
(`CLAUDE.md §0.1 Infrastructure Fallback Pattern`):

- Redis down → `InMemoryHITLStore`, `InMemoryRequestStore`
- Kafka down → `InMemoryBroker`
- DB down → `InMemoryAuditStorage` — **blocked in `app_env=production`**

These fallbacks are asserted in prose and exercised by unit tests, but the **activation behaviour
under a real outage was never chaos-tested**, and there was no ADR stating _which_ fallbacks are
allowed to degrade-open versus which must fail-closed. That distinction is a correctness and
compliance boundary, not an implementation detail: silently degrading the audit log in production
would lose immutable records (SOX/ISO), while refusing to start without Redis would be a needless
availability hit.

## Decision

Every in-memory fallback is classified **degrade-open** or **fail-closed**, and each classification
is validated by a Chaos Toolkit experiment.

1. **Degrade-open (availability over the dependency):** Redis (HITL/request stores) and Kafka
   (broker) fall back to their in-memory substitutes in **any** environment. The service stays
   healthy (`/health` → 200) and continues serving; the degradation is logged and observable.
   _Validated by_ `tests/chaos/experiments/redis-fallback-activation.yaml`.
2. **Fail-closed (integrity over availability):** the **audit log** must never use
   `InMemoryAuditStorage` in `app_env=production` — a missing DB pool raises `RuntimeError` at
   startup (`src/api/rest/main.py`) rather than silently buffering audit records that would be lost
   on pod restart. _Validated by_ `tests/chaos/experiments/db-audit-fallback-blocked.yaml`.
3. **A fallback's classification may only change via a new ADR.** Promoting the audit store to
   degrade-open, or demoting Redis to fail-closed, is an architectural decision — not a config flag.
4. **Every fallback path ships a chaos experiment** asserting its classification (degrade-open →
   service survives the outage; fail-closed → service refuses to proceed). New fallbacks add one.

## Consequences

### Positive

- The resilience pattern is now _evidenced_ (the experiments exercise real outages), not merely
  asserted — closing the gap between "we have fallbacks" and "the fallbacks behave correctly".
- The degrade-open / fail-closed boundary is explicit and ADR-gated, so an availability hack can't
  silently turn the audit log lossy in production.

### Negative / Trade-offs

- Two more experiments to maintain, and a small authoring cost per new fallback. Acceptable — it is
  the price of a _tested_ resilience claim.

### Neutral

- The experiments run against a deployed staging stack (Chaos Toolkit), not in PR unit CI; PR CI
  only validates their well-formedness (`tests/chaos/test_experiments_valid.py`). Wiring a
  lightweight fault into CI is tracked separately (STRENGTHENING-PLAN W2-10).

## Alternatives Considered

- **Leave fallbacks untested (status quo)** — rejected: an untested resilience pattern is a claim,
  not a control; the audit fail-closed path in particular is compliance-critical.
- **Make all fallbacks degrade-open for maximum availability** — rejected: losing audit records in
  production is an integrity/compliance failure that outweighs the availability gain.

## References

- `CLAUDE.md §0.1` (Infrastructure Fallback Pattern) · `src/api/rest/main.py` (audit prod-block)
- `reports/STRENGTHENING-PLAN.md` W2-9 · `tests/chaos/experiments/`
