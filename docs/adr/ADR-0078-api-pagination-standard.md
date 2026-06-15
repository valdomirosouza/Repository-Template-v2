# ADR-0078 — List-Endpoint Pagination Standard

**Status:** Accepted
**Date:** 2026-06-14
**Authors:** Valdomiro Souza
**Spec:** specs/api/SPEC-API-003-pagination.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0024](ADR-0024-api-versioning-strategy.md) (versioning), [ADR-0076](ADR-0076-api-structured-error-model-and-correlation.md) (error envelope)

## Context

`GET /v1/hitl/requests` returns the entire pending queue as a bare JSON array — no bounded page, no
disclosed total, and no convention for the next list endpoint. SPEC-API-003 specifies a pagination
standard; this ADR records the design, chosen to add paging **without breaking** existing callers (the
operator UI consumes the array body).

## Decision

1. **Offset/limit pagination, array body unchanged.** List endpoints accept `limit` (1–200, default =
   the resource's natural cap) and `offset` (≥0) query params and return the **page slice as the same
   array body**. Pagination metadata travels in **headers** — `X-Total-Count` and an RFC-5988 `Link`
   header with `rel="next"`/`"prev"` — so existing clients that ignore headers are unaffected
   (backward-compatible).
2. **Reusable helper.** One module (`src/api/rest/pagination.py`) validates the params (out-of-range ⇒
   `422 VALIDATION_ERROR` via the SPEC-API-001 envelope) and builds the headers, so every future list
   endpoint applies the identical contract.
3. **Default = no truncation.** When no params are supplied, `limit` defaults to the resource cap so the
   full list is returned as today; `X-Total-Count` is always set so any truncation is disclosed, never
   silent.
4. **Bounds via config** (`pagination_max_limit`, default 200).

## Consequences

### Positive

- Bounded response size and predictable paging; a consistent contract across list endpoints.
- Zero breakage: body shape is unchanged; the operator UI keeps working without changes.

### Negative / Trade-offs

- **Offset pagination** can skip/duplicate items if the list mutates between page reads. Acceptable for
  the bounded, slow-changing HITL queue; cursor/keyset pagination is the future upgrade.
- Metadata in headers (not the body) is slightly less discoverable than an envelope — accepted as the
  price of backward compatibility.

### Neutral

- Offset semantics are well understood and trivially testable.

## Alternatives Considered

- **Envelope body `{items, total, next}`.** Rejected for now — it breaks the array body and the operator
  UI; revisit if a future endpoint launches paginated from day one.
- **Cursor/keyset pagination.** Deferred — unnecessary for the bounded HITL queue; noted as the upgrade
  path for unbounded lists.
- **No pagination.** Rejected — unbounded responses as queues grow.

## Compliance & Risk

- **Controls affected:** OWASP A04 (design) — bounded responses; A09 (no PII in headers).
- **Data classification impact:** none — headers carry counts/offsets only (L4).
- **Autonomy impact:** none — no `src/agents/` or `src/guardrails/` change; no AI-safety phase.
- **Review/expiry:** permanent; revisit when adopting cursor pagination.

## Related

- `specs/api/SPEC-API-003-pagination.md`
- `docs/api/api-standards.md` (Pagination — Target → Current)
- `src/api/rest/routers/hitl.py` · `docs/adr/adr-review-checklist.md`
