# API Error Model

> **Owner:** Platform / Tech Lead | **Scope:** synchronous REST error responses
> **Status:** **Implemented** (ADR-0076 / SPEC-API-001). The structured envelope below is what the
> reference service now returns for every non-2xx response, with `X-Request-ID` on every response.
> The pre-ADR-0076 "Legacy default shape" section is kept only to explain the migration.

See `docs/api/api-standards.md` for the broader conventions and `skills/api/rest-api-design.md` for
status-code guidance. Schema: `docs/api/openapi/v1/openapi.yaml` (`components/schemas/Error`);
implementation: `src/api/rest/errors.py` + `src/api/rest/request_context.py`.

---

## Legacy default shape (pre-ADR-0076 — for migration context only)

Before ADR-0076 the service returned the FastAPI framework defaults (no envelope).

**Application/HTTP errors** (`HTTPException`) — single `detail` string:

```json
{ "detail": "Request 550e8400-… not found." }
```

Emitted by, e.g., `src/api/rest/routers/requests.py` (404) and `src/api/rest/auth.py` (401).

**Validation errors** (Pydantic, 422) — FastAPI's structured list:

```json
{
  "detail": [
    {
      "loc": ["body", "payload"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Rate limit** (429) — slowapi handler, with `X-RateLimit-*` headers.
**Backpressure** (503) — agent semaphore exhausted, with a `Retry-After` header.

### Properties of the current model

- **Correlation:** via OpenTelemetry `trace_id` in logs (`src/observability/logger.py`), **not** a
  field in the error body and **not** an `X-Request-ID` header.
- **PII:** error `detail` strings must never contain unmasked PII (CLAUDE.md §3.1). Today this is a
  convention enforced by review, not by a guard — see the Target.
- **Error codes:** none — clients must branch on HTTP status + parse `detail` text (brittle).

---

## Status code semantics

| Status | Meaning                          | Source                                   |
| ------ | -------------------------------- | ---------------------------------------- |
| 400    | Malformed request                | explicit `HTTPException`                 |
| 401    | Missing/invalid credentials      | `src/api/rest/auth.py` `_unauthorized()` |
| 403    | Authenticated but not permitted  | ownership/RBAC check (OWASP A01)         |
| 404    | Resource not found / TTL-expired | routers                                  |
| 409    | Conflict (idempotency/state)     | _Target_                                 |
| 422    | Validation failure               | FastAPI/Pydantic                         |
| 429    | Rate limited                     | slowapi (`src/api/rest/_limiter.py`)     |
| 500    | Unhandled server error           | framework                                |
| 503    | Overload / dependency down       | agent semaphore (`Retry-After`)          |

---

## Error model (implemented — ADR-0076)

A single, machine-parseable envelope across all non-2xx responses (RFC 9457 _problem+json_ flavour,
served as `application/json`), so clients branch on a stable `code` rather than on prose:

```json
{
  "type": "https://errors.example.com/request-not-found",
  "title": "Request not found",
  "status": 404,
  "code": "REQUEST_NOT_FOUND",
  "detail": "Request 550e8400-… not found.",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "errors": [{ "field": "payload", "message": "field required" }]
}
```

| Field      | Required | Notes                                                                |
| ---------- | -------- | -------------------------------------------------------------------- |
| `status`   | yes      | mirrors the HTTP status                                              |
| `code`     | yes      | stable, enumerated, screaming-snake — the client's branch key        |
| `title`    | yes      | short, human-readable, stable for a given `code`                     |
| `detail`   | no       | instance-specific; **PII-masked**                                    |
| `trace_id` | yes      | OTel trace id, for support correlation                               |
| `type`     | no       | URI categorising the error                                           |
| `errors[]` | no       | field-level validation problems (replaces the raw 422 `detail` list) |

The envelope also includes `request_id` (the `X-Request-ID` correlation id) — required.

### How it is implemented (ADR-0076)

1. ✅ App-wide exception handlers map `HTTPException`, `RequestValidationError`, `RateLimitExceeded`,
   and a catch-all `Exception` to the envelope, injecting `request_id`/`trace_id`
   (`src/api/rest/errors.py`).
2. ✅ `components/schemas/Error` is defined in `docs/api/openapi/v1/openapi.yaml` and referenced from
   the documented non-2xx responses, with an example and the published `code` enum.
3. ✅ Error `detail`/`errors[]` are PII-masked (`pii_filter`); covered by `tests/unit/api/test_error_model.py`.
4. ✅ The `code` enumeration is part of the contract; additions are backward-compatible, removals/renames
   are breaking (→ new API version, ADR-0024).

---

## Related

- `docs/api/api-standards.md`
- `docs/api/openapi/v1/openapi.yaml`
- `src/observability/logger.py` — where `trace_id` originates
- `src/guardrails/pii_filter.py` — masking that must cover error text
