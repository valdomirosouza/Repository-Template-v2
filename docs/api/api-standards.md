# REST API Standards

> **Owner:** Platform / Tech Lead | **Scope:** all synchronous REST endpoints (`/v1/...`)
> **Status:** Living standard. Sections marked **Current** describe what the reference service does
> today; sections marked **Target** are the agreed direction with an explicit adoption path — they
> are NOT yet enforced. Do not cite a Target rule as if it were implemented (CLAUDE.md §3.6).

This complements the implementation guidance in `skills/api/rest-api-design.md` and the event/async
conventions in `specs/api/async-api-design.md`. The machine-readable contract is
`docs/api/openapi/v1/openapi.yaml`. Error semantics have their own page: `docs/api/error-model.md`.

---

## 1. Versioning — **Current**

- All routes are namespaced under a major version prefix: `/v1/...` (`/v1/requests`, `/v1/hitl`, `/health`).
- Breaking changes ship under a new prefix (`/v2`); additive changes stay in `/v1`.
- The OpenAPI `info.version` tracks the spec revision, independent of the route prefix.

## 2. Resource & method conventions — **Current**

| Concern                 | Convention                                                            |
| ----------------------- | --------------------------------------------------------------------- |
| Resource naming         | plural nouns (`/requests`, `/hitl/requests`)                          |
| Async accept            | `POST` returning **202 Accepted** + a resource id when work is queued |
| Sync create             | `POST` returning **201 Created** when the resource exists on return   |
| Validation failure      | **422 Unprocessable Entity** (FastAPI/Pydantic)                       |
| Not found               | **404**                                                               |
| Overload / backpressure | **503** + `Retry-After` (agent semaphore exhausted)                   |
| Rate limited            | **429** (slowapi) — see §6                                            |

Status-code table and router layout are detailed in `skills/api/rest-api-design.md`.

## 3. Request correlation — **Current**

- Correlation is carried by **OpenTelemetry**: every request is auto-instrumented
  (`FastAPIInstrumentor`, `src/api/rest/main.py`) and logs include `trace_id` / `span_id`
  (`src/observability/logger.py`).
- `X-Request-ID` is set on every response and accepted inbound (see Correlation below, ADR-0076).
  Note `request_id` in HITL **routes** is a domain resource id (the HITL request), distinct from the
  transport correlation `request_id` in the error envelope / `X-Request-ID` header.

### Correlation — **Current** (ADR-0076)

- `RequestContextMiddleware` (`src/api/rest/request_context.py`) accepts an inbound `X-Request-ID`
  (validated to printable ASCII ≤128 chars) or generates a UUIDv4, sets it on **every** response, and
  binds it into the log/trace context (`src/observability/request_context.py`). The same value appears
  as `request_id` in the error envelope (`docs/api/error-model.md`).

## 4. Authentication & authorization — **Current**

- Bearer-token auth helper in `src/api/rest/auth.py`; unauthenticated requests get **401** via a
  shared `_unauthorized()` helper.
- Per-endpoint auth requirements belong in the OpenAPI `security` blocks. Enforce OWASP A01 at every
  boundary (ownership/RBAC checks) — see CLAUDE.md §3.2 and `skills/devsecops/owasp-top10.md`.

## 5. Pagination — **Current** (ADR-0078)

List endpoints use **offset/limit** pagination with a **backward-compatible array body**: optional
`limit` (1–200) and `offset` (≥0) query params slice the list, and `X-Total-Count` plus an RFC-5988
`Link` header (`rel="next"`/`"prev"`) disclose the total and further pages. No params returns the full
list (unchanged body). Implemented for `GET /v1/hitl/requests`; reusable helper:
`src/api/rest/pagination.py`. Cursor/keyset pagination is the future upgrade for unbounded lists
(`specs/api/SPEC-API-003-pagination.md`).

## 6. Rate limiting — **Current**

- `slowapi` limiter (`src/api/rest/_limiter.py`) buckets by JWT `sub` (authenticated) or client IP.
- Default budget: `rate_limit_requests_per_minute = 60` (`src/shared/config.py`).
- Over-budget → **429** via slowapi's handler (registered in `src/api/rest/main.py`); slowapi emits
  standard `X-RateLimit-*` headers. The agent-concurrency backpressure path returns **503** with an
  explicit `Retry-After`.

### Rate limiting — **Target**

- Document the limit/window per endpoint in OpenAPI and guarantee `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, and `Retry-After` on every throttled response (see `docs/api/error-model.md`).

## 7. Idempotency — **Current** (ADR-0077)

- `POST /v1/requests` accepts an optional `Idempotency-Key` header (printable ASCII, 8–200 chars) and
  de-duplicates retried submissions within a TTL window (`idempotency_ttl_hours`, default 24h): a
  repeat with the same body replays the original `202`; a repeat with a different body returns `422`
  `IDEMPOTENCY_KEY_REUSED`. Backed by `src/agents/idempotency_store.py` (Redis `SET NX`, in-memory
  fallback — degrade-open, ADR-0075). See `specs/api/SPEC-API-002-idempotency-keys.md`.

## 8. PII & security at the boundary — **Current**

- Mask PII with `src/guardrails/pii_filter.py` before logging or publishing (CLAUDE.md §3.1).
- Validate all input with Pydantic at the boundary; never echo unmasked PII in an error `detail`.
- `/docs` (Swagger) is disabled outside non-prod; `/metrics` exposes Prometheus golden signals.

## 9. Contract governance — **Target**

- Lint the OpenAPI spec (e.g. Spectral) and add breaking-change detection + SDK-drift checks in CI
  (`contract-drift` already exists for events). Add an `api-contract` workflow when the REST surface
  grows. Every endpoint should carry request/response **examples** and reference the shared error
  schema from `docs/api/error-model.md`.

---

## Related

- `docs/api/error-model.md` — standard error response shape (current + target)
- `skills/api/rest-api-design.md` — implementation patterns
- `specs/api/async-api-design.md` — event envelope & topic naming
- `docs/api/openapi/v1/openapi.yaml` — machine-readable contract
