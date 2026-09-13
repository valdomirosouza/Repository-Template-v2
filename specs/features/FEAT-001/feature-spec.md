---
id: SPEC-FEAT-001
kind: feature-spec
status: implemented # draft | in-review | approved | implemented | superseded (ADR-0085)
owner: Tech Lead
issue: 357
governing_adrs: [ADR-0006, ADR-0043, ADR-0089]
new_adrs_required: []
implemented_by:
  - src/api/rest/middleware/golden_signals.py
  - src/api/rest/main.py
verified_by:
  - tests/unit/api/test_golden_signals_middleware.py
  - tests/integration/test_lifespan_wiring.py
related_specs:
  - docs/product/FEAT-001/discovery.md
  - docs/product/FEAT-001/nfr.md
  - specs/observability/agent-performance.md
last_updated: 2026-09-12
---

# Feature Spec: HTTP Golden Signals for the API Gateway

> **⚡ Agent-Generated:** drafted by Claude Code on 2026-09-12 (Wave 12 · W12-T4, Wave 13 · W13-T7).
> **Human Review Required:** Tech Lead (observability) — no security surface change.
> **Review Status:** implemented — back-filled as the worked example of `specs/features/`.
> **Reviewer:** Tech Lead | **Approved:** via PR #365 (Wave 12)

---

**FEAT-ID:** FEAT-001 | **Spec id:** SPEC-FEAT-001 | **Owner:** Tech Lead
**ADR References:** ADR-0006 (observability), ADR-0043 (no PII in telemetry), ADR-0089 (reachability invariant)
**NFR Reference:** `docs/product/FEAT-001/nfr.md`
**GitHub Issue:** #357
**Sprint:** Wave 12 (2026-09-12)

> This spec is the first living instance of the `specs/features/FEAT-{issue}/` convention that
> the 15-phase workflow, DoR/DoD and HITL-GOVERNANCE are written around. It is deliberately
> small so every section is real.

---

## 1. Goal & Success Metrics

### Goal

Every HTTP request to the API gateway is counted and timed by method, **route template** and
status, so Traffic, Errors and Latency (three of the four Golden Signals) exist for the REST
surface and the governance SLO endpoint can report availability from real data.

### Success Metrics

| Metric                                            | Baseline (before)       | Target                            | Measurement Method                          |
| ------------------------------------------------- | ----------------------- | --------------------------------- | ------------------------------------------- |
| `http_requests_total` populated in production     | never (0 series)        | every route within 1 min of boot  | Prometheus `count(http_requests_total) > 0` |
| `/v1/governance/slo-status` availability observed | `data_available: false` | real ratio                        | endpoint response                           |
| Label cardinality                                 | n/a                     | ≤ routes × methods × status codes | `count by (path)(http_requests_total)`      |

### Business Value Gate

- **Baseline metric:** API availability SLI unobservable (no request counter).
- **Target:** availability SLI computable per route from `http_requests_total`.
- **Measurement:** Prometheus recording rule `api:availability:ratio_5m` (existing SLO file).

---

## 2. User Stories & Acceptance Criteria

### Functional Requirements (EARS)

| FR    | Statement                                                                                                         | Priority |
| ----- | ----------------------------------------------------------------------------------------------------------------- | -------- |
| FR-01 | WHEN any HTTP request completes the system SHALL increment `http_requests_total{service,method,path,status_code}` | must     |
| FR-02 | WHEN any HTTP request completes the system SHALL observe its duration in `http_request_duration_seconds`          | must     |
| FR-03 | WHEN labelling `path` the system SHALL use the route template (`/v1/requests/{request_id}`), never the raw path   | must     |
| FR-04 | WHEN a handler raises an unhandled exception the system SHALL record the request with status `500`                | must     |
| FR-05 | WHEN the path is `/metrics` the system SHALL NOT record it (no self-scrape noise)                                 | should   |
| FR-06 | WHEN the application boots the system SHALL install the middleware outermost (ADR-0089 wiring invariant)          | must     |

### Acceptance Criteria (canonical)

| AC    | Covers       | Given / When / Then (one line)                                                           | Verified by                                                                                   |
| ----- | ------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| AC-01 | FR-01        | app with middleware / GET `/items/x` / counter for (`GET`, `/items/{item_id}`, 200) +1   | `tests/unit/api/test_golden_signals_middleware.py::test_records_route_template_not_raw_path`  |
| AC-02 | FR-03        | same / GET `/items/<uuid>` / no series whose `path` is the raw uuid path                 | same test                                                                                     |
| AC-03 | FR-04        | handler raises / GET / counter for status `500` +1 and the exception propagates          | `…::test_unhandled_exception_counts_as_500_and_propagates`                                    |
| AC-04 | FR-01        | unmatched route / GET `/nope` / counter for (`<unmatched>`, 404) +1                      | `…::test_records_error_status_and_unmatched_routes`                                           |
| AC-05 | FR-02, FR-05 | GET `/metrics` then GET `/items/x` / `/metrics` not counted, latency histogram sum grows | `…::test_metrics_endpoint_is_excluded_and_latency_observed`                                   |
| AC-06 | FR-06        | real lifespan booted offline / GET `/health` / middleware installed and counter +1       | `tests/integration/test_lifespan_wiring.py::test_http_golden_signals_middleware_is_installed` |

```gherkin
Feature: HTTP Golden Signals
  Scenario: a routed request is counted by its template
    Given the API gateway is running with GoldenSignalsMiddleware
    When a client calls GET /v1/requests/00000000-0000-0000-0000-000000000042
    Then http_requests_total{method="GET",path="/v1/requests/{request_id}",status_code="200"} increases by 1
    And no series carries the raw request id in its path label
```

---

## 3. API Contract Delta (OpenAPI)

None. No endpoint added or changed; `/metrics` already exposed the Prometheus registry.

---

## 4. Event Contract Delta (Avro)

None.

---

## 5. Data Model Changes

None.

---

## 6. Agent Configuration

N/A — the feature does not involve `src/agents/`.

---

## 7. Security & Privacy

### PII Classification

- **New PII fields introduced:** no. Labels are method, route _template_, status code and service name (ADR-0043: identifiers never reach telemetry).
- **DPIA/RIPD required:** no.

### Threat Surface Delta

| Threat                                        | Category    | Mitigation                                 | Residual Risk |
| --------------------------------------------- | ----------- | ------------------------------------------ | ------------- |
| Label-cardinality exhaustion via random paths | STRIDE: DoS | unmatched routes collapse to `<unmatched>` | Low           |

### OWASP Controls Required

- [x] A09 Logging & Monitoring — every 4xx/5xx now counted per route (complements request-id logs)

---

## 8. Observability

### New Prometheus Metrics

| Metric Name                     | Type      | Labels                             | Description                          |
| ------------------------------- | --------- | ---------------------------------- | ------------------------------------ |
| `http_requests_total`           | counter   | service, method, path, status_code | (existing definition, now populated) |
| `http_request_duration_seconds` | histogram | service, method, path              | (existing definition, now populated) |

### Grafana Panel Required

- [x] No — the Golden Signals dashboard already queries these series; they were empty.

---

## 9. Operational Readiness

### New Failure Modes

| Failure Mode                                 | Detection                             | Recovery                          | Runbook |
| -------------------------------------------- | ------------------------------------- | --------------------------------- | ------- |
| Middleware not installed (wiring regression) | `test_lifespan_wiring.py` fails in CI | fix `main.py`; ADR-0089 invariant | n/a     |

### SLO Impact

- **SLO affected:** api-gateway availability (now measurable).
- **Expected impact:** < 0.1 ms per request (in-process counter + histogram).

---

## 10. Implementation Notes

- Pure ASGI middleware (no `BaseHTTPMiddleware`) so streaming and background tasks are untouched.
- Registered last in `main.py` so it is outermost and sees every request, including 404s.

---

## 11. Requirement Coverage (gate)

**Requirement coverage footer (gate).** 6 FRs total · 6 mapped to ≥ 1 AC · **0 unmapped ⚠️**

---

## 12. Open Questions

None.

---

## 13. Assumptions

| #   | Assumption                                                                 | Owner     | Resolve by (phase) | Status    |
| --- | -------------------------------------------------------------------------- | --------- | ------------------ | --------- |
| A1  | Route templates keep label cardinality bounded for all current routers     | Tech Lead | 4 — Specification  | confirmed |
| A2  | The existing Golden Signals dashboard queries these metric names unchanged | SRE Lead  | 11 — Observability | confirmed |
