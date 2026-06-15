---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-API-003
title: List-endpoint pagination standard
version: 0.1.0
status: implemented # draft | in-review | approved | implemented | superseded
owner: valdomirosouza
created: 2026-06-14
source: Improvement plan Wave 4 — docs/api/api-standards.md "Pagination — Target"; issue #251
deployment_topology: monorepo-services
governing_adrs: [ADR-0024, ADR-0076]
new_adrs_required: [api-pagination-standard]
related_specs:
  [
    specs/api/SPEC-API-001-error-model-and-request-correlation.md,
    specs/ai/hitl-hotl.md,
  ]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-API-003 — List-endpoint pagination standard

> **One-line scope.** Give list endpoints a consistent, **backward-compatible** `limit`/`offset`
> pagination contract (with `X-Total-Count` + RFC-5988 `Link` headers), and apply it to
> `GET /v1/hitl/requests`.

## How `/deliver` reads this spec (section → phase)

| Spec section            | Feeds phase(s)                  | Gate                          |
| ----------------------- | ------------------------------- | ----------------------------- |
| §1–§4                   | 0 Intake · 1 Conception         | problem/value                 |
| §5 FR, §6 NFR           | 2 Discovery · 4 Specification   | FR→AC traceability            |
| §7, §14, new_adrs       | 5 Architecture                  | ADR authored                  |
| §8 Interface Contracts  | 4 Specification · 6 Development | contract-driven dev (OpenAPI) |
| §12 Acceptance Criteria | 8 Testing                       | test evidence                 |

---

## 1. Context & Problem

### 1.1 Problem statement

`GET /v1/hitl/requests` returns the **entire** pending queue as a bare JSON array. There is no way for
a client to fetch a bounded page, no disclosed total, and no convention for the next list endpoint to
follow. `docs/api/api-standards.md` lists pagination as a Target.

### 1.2 Research / product question

Can we add bounded paging to list endpoints **without breaking** existing callers (the operator UI
consumes the bare array)?

### 1.3 Why now / motivation

Establishing one pagination convention now — before more list endpoints exist — keeps the API
consistent and bounds response size as queues grow.

### 1.4 Deployment topology decision

`monorepo-services` — implemented in the existing api-gateway (`src/api/rest/`).

## 2. Goals & Success Metrics

| ID   | Goal                             | Measure of success                                         |
| ---- | -------------------------------- | ---------------------------------------------------------- |
| G-01 | Bounded paging on list endpoints | `limit`/`offset` return the correct slice                  |
| G-02 | Backward-compatible              | No params ⇒ existing callers get the same array body       |
| G-03 | Truncation is never silent       | `X-Total-Count` + `Link` headers always disclose the total |

## 3. Non-Goals / Out of Scope

- **Not** cursor/keyset pagination (offset is adequate for the bounded HITL queue; cursor is a future
  enhancement noted in the ADR).
- **Not** changing the response **body** shape (stays an array — that is what keeps it compatible).
- **Not** paginating non-list endpoints.

## 4. Consumers & Personas

| Consumer       | Need                                          |
| -------------- | --------------------------------------------- |
| Operator UI    | Fetch the queue (today: all; future: by page) |
| API client/SDK | Page through large result sets predictably    |

## 5. Functional Requirements

| ID    | Requirement (EARS)                                                                                                                                 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | WHEN `limit`/`offset` query params are supplied, the system SHALL return that slice of the list in order.                                          |
| FR-02 | WHEN neither param is supplied, the system SHALL return the full list as today (default `limit` = the queue cap), preserving the array body.       |
| FR-03 | The system SHALL set `X-Total-Count` to the total item count and emit a `Link` header (`rel="next"`/`"prev"`) when further pages exist (RFC 5988). |
| FR-04 | WHEN `limit` is out of range (`<1` or `>200`) or `offset` `<0`, the system SHALL return `422 VALIDATION_ERROR` (the SPEC-API-001 envelope).        |
| FR-05 | The pagination helper SHALL be reusable (one module) so future list endpoints apply the same contract.                                             |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                 |
| ------ | --------------------------------------------------------------------------- |
| NFR-01 | Slicing is O(page); negligible overhead for the bounded HITL queue.         |
| NFR-02 | Coverage ≥ 80% for the pagination helper + endpoint (CLAUDE.md §3.5).       |
| NFR-03 | Bounds via config (`pagination_max_limit`, default 200) — no magic numbers. |
| NFR-04 | No PII added; only counts/offsets in headers.                               |

## 7. Architecture

A small `src/api/rest/pagination.py`: validates `limit`/`offset` (→ 422 via the envelope on bad input)
and builds the `Link`/`X-Total-Count` headers for a given total + page. The HITL list handler calls
`gateway.list_pending()`, slices, sets headers, returns the page array. Body shape unchanged.

## 8. Interface Contracts _(gate: contract-driven dev)_

| Method | Path              | New params                          | Body             | New headers             |
| ------ | ----------------- | ----------------------------------- | ---------------- | ----------------------- |
| GET    | /v1/hitl/requests | `limit` (1–200), `offset` (≥0), opt | array (as today) | `X-Total-Count`, `Link` |

OpenAPI: document the two query params and the two response headers (additive, ADR-0024). Regenerate
the TS client.

## 9. Data Model

No new persisted entity. Pagination is computed over `list_pending()` results.

## 10. Golden Signals & SLO Definitions

No new SLO. Response size becomes bounded by `limit`; no threshold change.

## 11. Governance, Privacy & Security

| Concern | Control                                         | Maps to         |
| ------- | ----------------------------------------------- | --------------- |
| PII     | headers carry counts only, never PII            | ADR-0012        |
| Abuse   | `limit` capped at 200 — bounds response size    | threat-model.md |
| Auth    | endpoint still requires the `hitl-operator` JWT | specs/security/ |

STRIDE on the new inputs (`limit`,`offset`): validated integers in range; no injection surface. No
`src/agents/`/`src/guardrails/` change → no Phase 10.

## 12. Acceptance Criteria _(gate: dry-run validation)_

| ID    | Acceptance criterion (WHEN … THEN …)                                                               | Covers FR(s) |
| ----- | -------------------------------------------------------------------------------------------------- | ------------ |
| AC-01 | WHEN `?limit=2&offset=1` over a 5-item queue, THEN 2 items (the 2nd–3rd) are returned in order.    | FR-01        |
| AC-02 | WHEN no params, THEN the full queue array is returned (unchanged body).                            | FR-02        |
| AC-03 | WHEN a page has more items beyond it, THEN `X-Total-Count` = total and a `rel="next"` Link is set. | FR-03        |
| AC-04 | WHEN `limit=0` or `limit=999` or `offset=-1`, THEN `422 VALIDATION_ERROR`.                         | FR-04        |
| AC-05 | WHEN the helper is used by a second (test) endpoint, THEN the same headers/validation apply.       | FR-05        |

> **Requirement coverage footer (gate).** 5 FRs total · 5 mapped to ≥ 1 AC · **0 unmapped ✅**

## 13. Risks & Limitations

- **Offset pagination** can skip/duplicate items if the underlying queue mutates between pages.
  Acceptable for the bounded, slow-changing HITL queue; cursor pagination is the future upgrade (ADR).

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0024 (versioning), ADR-0076 (error envelope).
- **Adds:** one ADR — _"List-endpoint pagination standard"_ (`api-pagination-standard`).
- **Produces:** `src/api/rest/pagination.py`, HITL handler change, config key, OpenAPI params/headers,
  regenerated TS client, tests, and a promotion of `api-standards.md` Pagination Target → Current.

## 15. Open Questions

1. Add cursor/keyset pagination later for unbounded lists? (Lean: yes when the first unbounded list
   endpoint appears; offset is fine for HITL now.)

## 16. References

- `docs/api/api-standards.md` (Pagination — Target) · RFC 5988 (Web Linking)
- `src/api/rest/routers/hitl.py` · `src/agents/hitl_store.py`
