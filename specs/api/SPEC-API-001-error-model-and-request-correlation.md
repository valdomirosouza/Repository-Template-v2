---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-API-001
title: Structured API error model and request correlation (X-Request-ID)
version: 0.1.0
status: approved # draft | in-review | approved | implemented | superseded
owner: valdomirosouza
created: 2026-06-14
source: Improvement plan Wave 3/4 — docs/api/error-model.md "Target"; issue #251
deployment_topology: monorepo-services
governing_adrs: [ADR-0004, ADR-0012, ADR-0024, ADR-0026, ADR-0029]
new_adrs_required: [api-structured-error-model-and-correlation]
related_specs:
  [
    specs/api/async-api-design.md,
    specs/security/threat-model.md,
    specs/privacy/pii-inventory.md,
  ]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-API-001 — Structured API error model and request correlation (X-Request-ID)

> **One-line scope.** Replace the FastAPI default error responses with a single, stable,
> machine-parseable error envelope and add end-to-end request correlation (`X-Request-ID`), so
> clients branch on a stable `code` and every error is traceable to one request — without leaking PII.

## How `/deliver` reads this spec (section → phase)

| Spec section            | Feeds /deliver phase(s)         | Gate it satisfies             |
| ----------------------- | ------------------------------- | ----------------------------- |
| §1–§4                   | 0 Intake · 1 Conception         | problem/value/risk recorded   |
| §5 FR, §6 NFR           | 2 Discovery · 4 Specification   | discovery + nfr; FR→AC trace  |
| §7, §14, new_adrs       | 5 Architecture                  | ADR authored & accepted       |
| §8 Interface Contracts  | 4 Specification · 6 Development | contract-driven dev (OpenAPI) |
| §9 Data Model           | 6 Development                   | schema validation             |
| §10 Golden Signals      | 11 Observability                | SLOs + PRR                    |
| §11 Governance/Security | 9 DevSecOps                     | STRIDE; privacy review        |
| §12 Acceptance Criteria | 8 Testing                       | dry-run/test evidence         |

---

## 1. Context & Problem

### 1.1 Problem statement

The REST API returns FastAPI defaults: application errors are a bare `{"detail": "<string>"}` and
validation errors a `{"detail": [ {loc, msg, type} ]}` list (see `docs/api/error-model.md` "Current").
Clients must branch on HTTP status and **parse prose** — brittle and unstable. There is **no error
code**, no correlation field in the body, and **no `X-Request-ID`**: correlation today relies solely
on the OpenTelemetry `trace_id` in server logs (`src/observability/logger.py`), which an API caller or
support engineer cannot see from a response. When something fails, there is no stable identifier the
caller can quote to find the exact request in logs/traces.

### 1.2 Research / product question

Can we give every non-2xx response a stable, documented shape (a `code` + a correlation id) that
clients and support can rely on, without changing business behaviour and without leaking PII?

### 1.3 Why now / motivation

Wave 3 documented this as the **Target** in `docs/api/api-standards.md` and `docs/api/error-model.md`;
Wave 4 confirmed it is still absent in `src/api/`. Establishing the contract now — while there are no
external clients depending on the default shape — avoids a harder breaking change later, and unblocks
idempotency/pagination work that will reuse the same envelope and correlation plumbing.

### 1.4 Deployment topology decision

`monorepo-services` — implemented in the existing api-gateway (`src/api/rest/`), reusing the current
CI/CD and governance. No new service.

## 2. Goals & Success Metrics

| ID   | Goal                                                       | Measure of success                                                             |
| ---- | ---------------------------------------------------------- | ------------------------------------------------------------------------------ |
| G-01 | Every non-2xx response has one stable, documented envelope | 100% of error responses validate against `components/schemas/Error` in OpenAPI |
| G-02 | Every request is correlatable end-to-end                   | 100% of responses carry `X-Request-ID`; it appears in the matching log/trace   |
| G-03 | No PII leaks through error responses                       | PII-leakage test suite green; `detail`/`errors[]` masked                       |
| G-04 | No business-behaviour change                               | All existing tests pass with only their asserted error **shape** updated       |

## 3. Non-Goals / Out of Scope

- **Not** changing which conditions produce which HTTP status (no new/changed business rules).
- **Not** implementing idempotency keys or pagination (separate specs; they reuse this envelope/correlation).
- **Not** localising/translating `title`/`detail`.
- **Not** changing the async event envelope (`specs/api/async-api-design.md` already has `trace_id`).
- **Not** versioning bump to `/v2` — this is an additive contract on the existing `/v1` error responses
  (see §13 on the compatibility trade-off).

## 4. Consumers & Personas

| Consumer                   | Need from this system                                                           |
| -------------------------- | ------------------------------------------------------------------------------- |
| API client / frontend      | Branch on a stable `code`; surface a support id to the user                     |
| HITL operator UI           | Show a correlation id when a decision call fails                                |
| Support / on-call engineer | Take a caller-supplied `X-Request-ID` and find the exact request in logs/traces |
| Auditor                    | Confirm errors are logged with a correlation id and no PII (OWASP A09)          |

## 5. Functional Requirements

| ID    | Requirement (EARS)                                                                                                                                                                                                 |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-01 | WHEN any handler raises `HTTPException`, the system SHALL return the structured error envelope (§9.1) with the mapped `status`, a stable `code`, a `title`, an optional `detail`, and the `request_id`/`trace_id`. |
| FR-02 | WHEN request validation fails (Pydantic/`RequestValidationError`), the system SHALL return the envelope with `status=422`, `code=VALIDATION_ERROR`, and an `errors[]` array of `{field, message}` items.           |
| FR-03 | WHEN an unhandled exception occurs, the system SHALL return the envelope with `status=500`, `code=INTERNAL_ERROR`, and SHALL NOT include exception internals or stack traces in `detail`.                          |
| FR-04 | The system SHALL accept an inbound `X-Request-ID` header, validate it (printable ASCII, ≤128 chars), and reuse it; WHEN absent or invalid, the system SHALL generate a UUIDv4.                                     |
| FR-05 | The system SHALL set `X-Request-ID` on **every** response (success and error) and SHALL include the same value as `request_id` in the error envelope.                                                              |
| FR-06 | The system SHALL bind the request id into the logging/trace context so every log line and span for the request carries it alongside `trace_id`.                                                                    |
| FR-07 | WHEN building any error `detail` or `errors[]`, the system SHALL mask PII via `pii_filter` so no unmasked PII appears in a response body or header.                                                                |
| FR-08 | The system SHALL preserve existing rate-limit (429, slowapi) and backpressure (503 + `Retry-After`) behaviour, re-expressed through the envelope.                                                                  |
| FR-09 | The error `code` enumeration SHALL be published in the OpenAPI contract; adding a code is backward-compatible, removing/renaming one is breaking (→ API version bump per ADR-0024).                                |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                                                                               |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | Correlation middleware overhead SHALL be ≤ 1 ms p99 per request (negligible vs the orchestration path).                                                   |
| NFR-02 | Unit + integration coverage ≥ 80% for new modules (CLAUDE.md §3.5); error mapping and middleware fully covered.                                           |
| NFR-03 | Config via env only (no hard-coded values); `X-Request-ID` header name and max length documented in `.env.example`/`config.py`.                           |
| NFR-04 | Logs SHALL carry `request_id`, `trace_id`, `service`, `operation`, status; **no PII** (OWASP A09).                                                        |
| NFR-05 | The envelope SHALL be defined once (a single Pydantic model + OpenAPI `components/schemas/Error`) and reused by all routers — no per-router error shapes. |
| NFR-06 | **PII:** `detail`, `errors[].message`, and any header value are untrusted output — masked before emit (L1–L4 per `specs/privacy/pii-inventory.md`).       |
| NFR-07 | Deterministic, dependency-light: no new runtime dependency beyond what FastAPI/Starlette already provide (a `ContextVar` for propagation).                |

## 7. Architecture

Three additions inside `src/api/rest/`, no change to business logic:

```
            ┌──────────────── RequestContextMiddleware (ASGI) ───────────────┐
inbound ───►│ read/validate/generate X-Request-ID → ContextVar + log binding │───► routers
            │ on response: set X-Request-ID header                            │◄─── responses
            └────────────────────────────────────────────────────────────────┘
                         ▲                                  ▲
         exception handlers (HTTPException,        ErrorResponse model (§9.1)
         RequestValidationError, Exception)  ───►  + OpenAPI components/schemas/Error
                         │
                  pii_filter.mask  (FR-07)
```

- **`RequestContextMiddleware`** — resolves the request id (FR-04), stores it in a `ContextVar` read by
  the logger (extends `src/observability/logger.py`), and sets the response header (FR-05/06).
- **Exception handlers** — registered on the app (where only the slowapi handler exists today,
  `src/api/rest/main.py`): map `HTTPException`, `RequestValidationError`, and a catch-all `Exception`
  to `ErrorResponse` (FR-01/02/03), pulling `request_id`/`trace_id` from context.
- **`ErrorResponse`** — one Pydantic model (§9.1), the single source for the OpenAPI error schema.
- Optional: a small typed domain-error base (`AppError(code, status, title)`) so domain code raises
  semantic errors that map cleanly to the envelope (keeps `code`s stable).

Aligns with ADR-0004 (observability) and ADR-0024 (versioning). The envelope choice (RFC 9457
problem+json flavour) is an architectural decision → **new ADR** (`new_adrs_required`).

## 8. Interface Contracts _(gate: contract-driven dev)_

This changes **response shape only** — no new routes. Applies to all existing endpoints.

| Aspect            | Contract                                                                                                                                                                    |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Error body        | `components/schemas/Error` (§9.1) on every non-2xx response in `docs/api/openapi/v1/openapi.yaml`, with examples                                                            |
| `X-Request-ID`    | response header on **all** responses; accepted as request header                                                                                                            |
| Error `code` enum | published in OpenAPI; values: `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `CONFLICT`, `RATE_LIMITED`, `UNAVAILABLE`, `INTERNAL_ERROR` (extend additively) |

OpenAPI is regenerated/updated from this section; the `contract-drift` gate must stay green.

## 9. Data Model

### 9.1 Entities / payloads

`ErrorResponse` (problem+json flavour):

```json
{
  "status": 404,
  "code": "NOT_FOUND",
  "title": "Request not found",
  "detail": "Request 550e8400-… not found.",
  "request_id": "0af7-…",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "errors": [{ "field": "payload", "message": "field required" }]
}
```

`status` (int, required), `code` (enum, required), `title` (str, required, stable per code),
`detail` (str, optional, **masked**), `request_id` (str, required), `trace_id` (str, required),
`errors[]` (optional; `{field, message}` for validation).

### 9.2 Storage key/schema convention

None — stateless. `request_id` propagates via a `ContextVar` (request-scoped), never persisted by this
feature (it already appears in logs/traces and audit `metadata` where relevant).

### 9.3 Retention

N/A — `request_id` lives only in logs/traces, governed by existing log retention
(`specs/privacy/data-retention.md`).

### 9.4 Governance/response metadata

`request_id` + `trace_id` are the response-side correlation metadata; both are L3 (technical
identifier), safe to return.

## 10. Golden Signals & SLO Definitions _(gate: observability)_

| Signal     | Derivation                                         | Exposed as       |
| ---------- | -------------------------------------------------- | ---------------- |
| Traffic    | request rate by route/method/status                | existing metrics |
| Latency    | per-route latency incl. middleware (NFR-01 budget) | P50/P95/P99      |
| Error      | error rate, now also sliceable by error `code`     | `error_rate`     |
| Saturation | unchanged                                          | existing metrics |

No new SLO thresholds; this improves error **observability** (slice by `code`). No HITL-flipping
threshold introduced.

## 11. Governance, Privacy & Security _(gate: threat & privacy review)_

| Concern                     | Control in this spec                                             | Maps to                        |
| --------------------------- | ---------------------------------------------------------------- | ------------------------------ |
| Human oversight (HITL/HOTL) | Unchanged — no autonomy/guardrail behaviour touched (N/A)        | ADR-0011                       |
| PII (classify, mask)        | FR-07/NFR-06 — mask all `detail`/`errors[]`/headers before emit  | ADR-0012, specs/privacy/       |
| Auditability                | error logs carry `request_id`+`trace_id`, no PII (OWASP A09)     | ADR-0026                       |
| Authn / abuse               | preserve 401/403/429; validate `X-Request-ID` (header injection) | specs/security/threat-model.md |
| Cost envelope               | negligible (in-process middleware)                               | ADR-0020                       |
| Pipeline security           | SAST/SCA/secret/SBOM unchanged; no new runtime dep               | ADR-0029                       |

**STRIDE on the new untrusted input (`X-Request-ID` header):** Tampering/Injection — validate to
printable ASCII ≤128 chars and never reflect it into HTML/log-forging contexts unescaped (it is set
as a response header and a structured log field only). Information disclosure — `detail` must be
masked and must never contain stack traces (FR-03/07). Does **not** touch `src/agents/` or
`src/guardrails/`, so Phase 10 (AI Safety) is **not** triggered.

## 12. Acceptance Criteria _(gate: dry-run validation)_

| ID    | Acceptance criterion (WHEN … THEN …)                                                                                                 | Covers FR(s) |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------ |
| AC-01 | WHEN GET an unknown request id, THEN response is 404 with `code=NOT_FOUND` and a valid envelope + `X-Request-ID`.                    | FR-01, FR-05 |
| AC-02 | WHEN POST an invalid body, THEN 422 with `code=VALIDATION_ERROR` and `errors[]` listing the bad fields.                              | FR-02        |
| AC-03 | WHEN a handler raises an unexpected error, THEN 500 with `code=INTERNAL_ERROR` and no stack trace/internals in `detail`.             | FR-03        |
| AC-04 | WHEN a client sends `X-Request-ID: abc123`, THEN the response echoes `X-Request-ID: abc123` and the envelope `request_id` equals it. | FR-04, FR-05 |
| AC-05 | WHEN no `X-Request-ID` is sent, THEN the response carries a generated UUIDv4 and the matching server log line shows the same id.     | FR-04, FR-06 |
| AC-06 | WHEN an error `detail` would contain a value matching a PII field, THEN the emitted `detail` is masked.                              | FR-07        |
| AC-07 | WHEN the rate limit is exceeded, THEN 429 with `code=RATE_LIMITED`; WHEN backpressure, 503 `code=UNAVAILABLE` with `Retry-After`.    | FR-08        |
| AC-08 | WHEN the OpenAPI spec is linted, THEN every non-2xx response references `components/schemas/Error` and the `code` enum is published. | FR-09        |

> **Requirement coverage footer (gate).** 9 FRs total · 9 mapped to ≥ 1 AC · **0 unmapped ✅**.

## 13. Risks & Limitations

- **Breaking response shape.** Changing `{detail}` → envelope breaks any client parsing the old shape.
  Mitigation: there are no external clients yet; the frontend is in-repo and updated in the same change;
  document in CHANGELOG and the OpenAPI contract. Trade-off accepted now to avoid a costlier change later
  (→ ADR consequence).
- **Header injection / log forging** via `X-Request-ID` — mitigated by validation (FR-04) and treating
  it as a structured field, never interpolated into log message strings.
- **Double-masking cost** is negligible; masking only runs on the error path.

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0004 (observability), ADR-0012 (PII masking), ADR-0024 (API versioning),
  ADR-0026 (audit), ADR-0029 (pipeline security).
- **Adds:** one ADR — _"Structured API error model (RFC 9457 flavour) + request correlation"_ — recording
  the envelope choice, the `code` enumeration policy, and the `X-Request-ID` contract
  (`new_adrs_required: api-structured-error-model-and-correlation`).
- **Produces:** updated `docs/api/openapi/v1/openapi.yaml` (`Error` schema + examples), `ErrorResponse`
  model + middleware + handlers in `src/api/rest/`, tests, `.env.example` entries, and a promotion of
  `docs/api/error-model.md` / `api-standards.md` sections from **Target** to **Current**.

## 15. Open Questions

1. Adopt the full RFC 9457 `application/problem+json` content-type, or keep `application/json` with the
   same body shape? (Recommend the latter initially to minimise client friction; decide in the ADR.)
2. Introduce the typed `AppError` domain hierarchy now, or only the handler-level mapping? (Recommend
   handler-level first; add `AppError` when the first domain code needs it.)
3. Should `request_id` also be written into audit `metadata` for HITL decisions, or is `trace_id` there
   sufficient? (Lean: add `request_id` for human-quotable correlation.)

## 16. References

- `docs/api/error-model.md`, `docs/api/api-standards.md` — the "Target" this spec formalises
- `docs/reference/request-lifecycle.md` — where errors arise on the critical path
- `src/observability/logger.py`, `src/api/rest/main.py`, `src/api/rest/_limiter.py` — current behaviour
- RFC 9457 (Problem Details for HTTP APIs); OWASP A09 (logging) / A04 (design)
- `specs/privacy/pii-inventory.md` — L1–L4 classification for masking
