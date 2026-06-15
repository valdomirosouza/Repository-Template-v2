# ADR-0076 — Structured API Error Model and Request Correlation (X-Request-ID)

**Status:** Accepted
**Date:** 2026-06-14
**Authors:** Valdomiro Souza
**Spec:** specs/api/SPEC-API-001-error-model-and-request-correlation.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0004](ADR-0004-observability-stack.md) (observability), [ADR-0012](ADR-0012-pii-masking-strategy.md) (PII masking), [ADR-0024](ADR-0024-api-versioning-strategy.md) (API versioning)

## Context

The REST API returned FastAPI defaults: a bare `{"detail": "<string>"}` for `HTTPException` and a
`{"detail": [...]}` list for validation errors. Clients had to branch on HTTP status and parse prose,
there was no stable error `code`, and no correlation identifier in the response body or headers —
correlation relied solely on the OpenTelemetry `trace_id` in server logs, invisible to a caller or a
support engineer. SPEC-API-001 specifies a single, stable, machine-parseable error envelope and an
`X-Request-ID` correlation contract. This ADR records the design decisions that spec requires.

## Decision

1. **Error envelope.** Every non-2xx response returns one shape — a single `ErrorResponse` Pydantic
   model, the sole source for the OpenAPI `components/schemas/Error`: `status`, a stable `code` (enum),
   `title`, optional **PII-masked** `detail`, `request_id`, `trace_id`, and an optional `errors[]`
   (`{field, message}`) for validation failures. Modelled on **RFC 9457 (Problem Details)** but served
   as plain `application/json` (not `application/problem+json`) to minimise client friction (Open
   Question #1 resolved in favour of plain JSON).
2. **Code enumeration policy.** `code` values are screaming-snake and enumerated in the OpenAPI
   contract. **Adding** a code is backward-compatible; **removing/renaming** one is breaking and
   requires an API version bump (ADR-0024). Initial set: `VALIDATION_ERROR`, `BAD_REQUEST`,
   `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`, `UNAVAILABLE`, `INTERNAL_ERROR`.
3. **Correlation.** A `RequestContextMiddleware` accepts an inbound `X-Request-ID` (validated to
   printable ASCII ≤128 chars), or generates a UUIDv4, stores it in a `ContextVar`, binds it into the
   structured logger, and sets it on **every** response. The same value appears as `request_id` in the
   error envelope. `trace_id` (OTel) is retained alongside it.
4. **Mapping, not behaviour.** App-wide exception handlers map `HTTPException`,
   `RequestValidationError`, `RateLimitExceeded`, and a catch-all `Exception` to the envelope. Which
   condition yields which HTTP status is unchanged; the 503-capacity `Retry-After` and slowapi 429
   rate-limit headers are preserved.
5. **No new runtime dependency** — only Starlette/FastAPI primitives and a `ContextVar`.
6. **Typed `AppError` hierarchy deferred** (Open Question #2): handler-level mapping ships first; a
   typed domain-error base is added when the first domain code needs it.

## Consequences

### Positive

- Clients branch on a stable `code`; users/support get a quotable `request_id` that ties a response to
  the exact log line and trace.
- One envelope, defined once, removes per-router error drift (NFR-05).
- Error rate becomes sliceable by `code`; correlation improves incident MTTR.

### Negative / Trade-offs

- **Breaking response shape.** Any client parsing the old `{detail}` must update. Accepted now because
  there are no external clients yet and the in-repo frontend's generated client surfaces errors
  generically; documented in the OpenAPI contract and CHANGELOG. Deferring would make the change costlier.
- A new untrusted input (`X-Request-ID`) — mitigated by validation and treating it strictly as a
  response header / structured log field (never interpolated into log strings).

### Neutral

- `request_id` is L3 (technical identifier), safe to return; it lives only in logs/traces, governed by
  existing log retention.

## Alternatives Considered

- **Keep FastAPI defaults.** Rejected — no stable code, no caller-visible correlation; the status quo
  the spec exists to fix.
- **`application/problem+json` content-type.** Deferred — same body, but the distinct content-type adds
  client friction for no immediate benefit; revisit if external API consumers need strict RFC 9457.
- **Rely on `trace_id` alone for correlation.** Rejected — not present in the response, and callers
  cannot supply their own id for cross-system correlation.

## Compliance & Risk

- **Controls affected:** OWASP A09 (every 4xx/5xx logged with `request_id`, no PII) — strengthened.
- **Data classification impact:** none new; `request_id`/`trace_id` are L3. `detail`/`errors[]` masked
  (ADR-0012) — no L1/L2 in responses.
- **Autonomy impact:** none — does not touch `src/agents/` or `src/guardrails/`; no AI-safety phase.
- **Review/expiry:** permanent; revisit only if adopting `problem+json` or an `AppError` hierarchy.

## Related

- `specs/api/SPEC-API-001-error-model-and-request-correlation.md`
- `docs/api/error-model.md` · `docs/api/api-standards.md` (Target → Current after implementation)
- `docs/adr/adr-review-checklist.md`
