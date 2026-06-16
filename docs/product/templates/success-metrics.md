# Success Metrics — FEAT-{id}

> **Owner:** Product Owner | **Phase:** 2 (Discovery) | **Status:** Draft | Under Review | Approved
> Copy to `docs/product/FEAT-{id}/success-metrics.md`. When agent-generated, prepend the
> Agent-Disclosure Header (see `docs/product/README.md`).
>
> Define how success will be measured **before** building, and wire each metric to an actual
> instrument (a Prometheus metric, a log field, an analytics event). A metric with no instrument is
> a wish, not a measure — see `skills/observability/otel-instrumentation.md`.

---

## North-star metric

| Field                | Value                                                  |
| -------------------- | ------------------------------------------------------ |
| **Metric**           | {the single number that best captures value delivered} |
| **Current baseline** | {today's value, with source}                           |
| **Target**           | {goal value}                                           |
| **Timeframe**        | {by when}                                              |

## Metric tree

| Type          | Metric                                                                 | Baseline | Target | Instrument (where it comes from)      |
| ------------- | ---------------------------------------------------------------------- | -------- | ------ | ------------------------------------- |
| **Leading**   | {early adoption/usage signal}                                          | {x}      | {y}    | {analytics event / Prometheus metric} |
| **Leading**   | {engagement signal}                                                    | {x}      | {y}    | {…}                                   |
| **Lagging**   | {business outcome}                                                     | {x}      | {y}    | {revenue / churn / CSAT source}       |
| **Guardrail** | {what must NOT get worse — e.g. p99 latency, error rate, cost/request} | {x}      | {≤ x}  | `docs/sre/slo/` / FinOps dashboard    |

## Counter-metrics (watch for gaming)

- {a metric that, if it moves the wrong way, means we optimised the wrong thing}

## Instrumentation checklist

- [ ] Each metric above has a named source (metric/log/event) that exists or is in scope of the spec
- [ ] Guardrail metrics are tied to an SLO or budget (`docs/sre/slo/`, `specs/sre/finops.md`)
- [ ] A dashboard panel or query is identified for review at the success-review date

---

## Related

- `docs/product/templates/value-hypothesis.md`
- `docs/product/templates/user-story-map.md` — AC → test → evidence mapping
- `docs/product/nfr-taxonomy.md` — classify guardrail metrics by NFR category + evidence/gate
- `skills/sre/golden-signals.md` · `specs/observability/dora-metrics.md`
