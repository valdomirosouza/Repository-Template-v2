# Discovery — FEAT-001 HTTP Golden Signals for the API Gateway

> **Phase:** 2 (Discovery) · **Issue:** #357 · **Spec:** `specs/features/FEAT-001/feature-spec.md` (SPEC-FEAT-001)
> **Owner:** Tech Lead · **Date:** 2026-09-12 · **Status:** approved (back-filled worked example, W13-T7)

## Problem

The Seven-Axis Review (2026-09-12) found `http_requests_total` and `http_request_duration_seconds`
defined in `src/observability/metrics.py` with zero callers and `src/api/rest/middleware/` empty.
Consequences: the Golden Signals dashboard panels for the API were blank, and
`GET /v1/governance/slo-status` returned `data_available: false` for availability because there
was no request counter to derive it from.

## Value hypothesis

If every request is counted and timed by route template, then the API availability SLI becomes
computable and on-call can distinguish "traffic dropped" from "errors rose" within one scrape
interval. Falsifiable: after deployment, `count(http_requests_total) > 0` and the SLO endpoint
reports a real ratio.

## Options considered

| Option                                        | Verdict  | Why                                                       |
| --------------------------------------------- | -------- | --------------------------------------------------------- |
| Rely on `FastAPIInstrumentor` OTel spans only | rejected | spans are sampled and exported; SLOs need a local counter |
| `BaseHTTPMiddleware`                          | rejected | buffers streaming responses, breaks background tasks      |
| Pure ASGI middleware calling `record_request` | chosen   | zero-copy, sees 404s, keeps existing metric definitions   |

## Assumptions (carried to spec §13)

- A1 Route templates bound label cardinality for every router.
- A2 The dashboard already queries these metric names.

## Open questions

None — resolved at Phase 4 (see spec §12).
