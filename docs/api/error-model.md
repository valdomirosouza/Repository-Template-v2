# API Error Model

> **Owner:** Platform / Tech Lead | **Scope:** synchronous REST error responses
> **Status:** **Current** = the shape the reference service returns today; **Target** = the agreed
> standard with an adoption path. Do not document a Target field as if clients can rely on it yet
> (CLAUDE.md §3.6).

See `docs/api/api-standards.md` for the broader conventions and `skills/api/rest-api-design.md` for
status-code guidance.

---

## Current error shape

The reference FastAPI service returns the framework defaults — there is no custom error envelope.

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

## Target error model

A single, machine-parseable envelope across all non-2xx responses (RFC 9457 _problem+json_ flavour),
so clients branch on a stable `code` rather than on prose:

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

### Adoption path

1. Add an app-wide exception handler that maps `HTTPException` and `RequestValidationError` to the
   envelope above and injects the current `trace_id`.
2. Define `components/schemas/Error` in `docs/api/openapi/v1/openapi.yaml` and reference it from every
   non-2xx response, with examples.
3. Add a guard/test asserting no error `detail` contains unmasked PII (extends `pii_filter`).
4. Publish the `code` enumeration as part of the API contract; treat additions as backward-compatible
   and removals/renames as breaking (→ new API version).

Until step 1 ships, **clients must treat the Current shape as the contract.**

---

## Related

- `docs/api/api-standards.md`
- `docs/api/openapi/v1/openapi.yaml`
- `src/observability/logger.py` — where `trace_id` originates
- `src/guardrails/pii_filter.py` — masking that must cover error text
