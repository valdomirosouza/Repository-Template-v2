---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-API-004 # SPEC-<DOMAIN>-<NNN>; unique; used by /deliver as the SLUG base
title: Read-only run-trace and SLO-status endpoints for the operator UI
version: 0.1.0
status: draft # draft | in-review | approved | implemented | superseded
owner: valdomirosouza # Product Owner or Tech Lead
created: 2026-06-16
source: GitHub issue #273 (part 5b) — operator UI needs an agent-run/trace view and an SLO/error-budget panel
deployment_topology: monorepo-services # registered service: api-gateway
governing_adrs: [ADR-0076, ADR-0011, ADR-0004] # error model · human oversight · observability
new_adrs_required: [] # no new architectural decision — reuses existing patterns
related_specs:
  [
    specs/api/SPEC-API-001-error-model-and-request-correlation.md,
    specs/system/request-pipeline.md,
    specs/ai/hitl-hotl.md,
  ]
slo_ref: docs/sre/slo/slo.yaml # SLO targets surfaced (read-only) by GET /v1/governance/slo-status
---

# SPEC-API-004 — Read-only run-trace and SLO-status endpoints

> **One-line scope.** Two authenticated, read-only GET endpoints — a per-request execution
> trace and an SLO-target/status panel — so the operator UI (issue #273) can render an
> agent-run view and an SLO/error-budget panel **without fabricating any data it cannot observe**.

## How `/deliver` reads this spec (section → phase)

| Spec section                                     | Feeds /deliver phase(s)         | Gate it satisfies                                 |
| ------------------------------------------------ | ------------------------------- | ------------------------------------------------- |
| §1 Context, §2 Goals, §3 Non-Goals, §4 Consumers | 0 Intake · 1 Conception         | problem/value/risk recorded                       |
| §5 FR, §6 NFR                                    | 2 Discovery · 4 Specification   | discovery + nfr; FR→AC traceability               |
| §7 Architecture, §14 ADR Impact                  | 5 Architecture                  | no new ADR (reuse only)                           |
| §8 Interface Contracts (gate)                    | 4 Specification · 6 Development | OpenAPI paths in docs/api/openapi/v1/openapi.yaml |
| §10 Golden Signals & SLO (gate)                  | 11 Observability                | reads existing slo.yaml; adds no new SLO          |
| §11 Governance/Privacy/Security (gate)           | 9 DevSecOps                     | STRIDE on the two read boundaries                 |
| §12 Acceptance Criteria (gate)                   | 8 Testing                       | dry-run evidence                                  |

---

## 1. Context & Problem

### 1.1 Problem statement

Issue #273 (part 5b) needs a frontend that renders (a) an **agent-run / trace view** for a single
submitted request and (b) an **SLO / error-budget panel**. The backend currently exposes only
`GET /v1/requests/{id}` (flat status) and `GET /v1/hitl/...`. There is no endpoint that returns a
request's **execution timeline**, and no endpoint that surfaces the **SLO definitions** the panel
must render. Without these two read-only endpoints the frontend has nothing real to draw.

### 1.2 Research / product question

Can we give the operator UI a faithful per-run trace and an SLO panel **using only data the running
service can actually observe today**, and explicitly mark the parts that require infrastructure we
do not yet have (a metrics-query/PromQL layer, request-id-indexed audit)?

### 1.3 Why now / motivation

The frontend PR for #273 is blocked on a stable contract. Shipping the two read endpoints + their
OpenAPI schema unblocks it and regenerates the TS client.

### 1.4 Deployment topology decision

`monorepo-services` — both endpoints live in the existing `api-gateway` FastAPI service. No new
service, no new registry entry.

## 2. Goals & Success Metrics

| ID   | Goal                                                  | Measure of success                                                                         |
| ---- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| G-01 | Expose a per-request execution trace                  | `GET /v1/runs/{request_id}` returns request state + a timeline of really-associated events |
| G-02 | Expose SLO targets for the SLO panel                  | `GET /v1/governance/slo-status` returns every service/SLO from `slo.yaml`                  |
| G-03 | **Never fabricate observed numbers (CLAUDE.md §3.6)** | Every value the service cannot compute carries an explicit `data_available: false` flag    |
| G-04 | Both endpoints are authenticated and read-only        | A request without a valid bearer JWT returns 401; only GET verbs are added                 |

## 3. Non-Goals / Out of Scope

- **No live SLO burn-rate / error-budget-remaining computation.** That needs a metrics-query
  (PromQL) layer the app does not have. We return SLO _targets_ and an honestly-flagged _observed_
  block; we do **not** invent observed compliance numbers.
- **No new audit indexing.** We do not add a request-id index to the audit store, and we do not
  modify `src/guardrails/**` or `src/agents/hitl_gateway.py` (dual-approval, CLAUDE.md §14).
- **No write/mutation.** Both endpoints are GET-only; no new outbound/external calls.
- **No persistence schema change / migration.**

## 4. Consumers & Personas

| Consumer                   | Need from this system                                                            |
| -------------------------- | -------------------------------------------------------------------------------- |
| Operator UI (frontend/web) | Per-run trace to render a run view; SLO list to render an SLO/error-budget panel |
| SRE / on-call              | Quick read of configured SLO targets and which observed signals are unavailable  |

## 5. Functional Requirements

| ID    | Requirement (EARS: WHEN … the system SHALL …)                                                                                                                                                                                                                                                                         |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | WHEN an authenticated caller GETs `/v1/runs/{request_id}` for a known request, the system SHALL return the request's `request_id`, `status`, `created_at`, `updated_at`, `result`, `error`.                                                                                                                           |
| FR-02 | WHEN returning a run, the system SHALL include a `timeline` array of `TraceEvent`s built **only** from audit events that can be _really_ associated with that request (see §9.1).                                                                                                                                     |
| FR-03 | WHEN the timeline is built by an approximate association strategy, the system SHALL set `timeline_association` to the strategy actually used and SHALL NOT imply exact linkage.                                                                                                                                       |
| FR-04 | WHEN the `request_id` is unknown (or its TTL has expired), the system SHALL return 404 using the ADR-0076 `ErrorResponse` envelope (`code: NOT_FOUND`).                                                                                                                                                               |
| FR-05 | WHEN an unauthenticated caller hits either endpoint, the system SHALL return 401 with the ADR-0076 envelope (`code: UNAUTHORIZED`).                                                                                                                                                                                   |
| FR-06 | WHEN an authenticated caller GETs `/v1/governance/slo-status`, the system SHALL return every service and SLO defined in `docs/sre/slo/slo.yaml` (name, sli_type, target/target_ms/target_max, window).                                                                                                                |
| FR-07 | WHEN a real observed value cannot be computed for an SLO, the system SHALL return `observed.data_available: false` with a human-readable `note`, and SHALL NEVER emit a fabricated number.                                                                                                                            |
| FR-08 | WHEN a real in-process observed sample _can_ be read from a Prometheus counter (api-gateway availability/error-rate from `http_requests_total`), the system SHALL return it with `data_available: true` and a `source` and `scope` that honestly describe it as a process-lifetime sample, not the 30-day SLO window. |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                            | Taxonomy / evidence                      |
| ------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| NFR-01 | Both endpoints are read-only (GET) and add no external/outbound HTTP calls (OWASP A10 unchanged).      | Security; no new url_allowlist boundary  |
| NFR-02 | `slo.yaml` is parsed at most once and cached in-process (module-level lazy cache).                     | Performance; avoid per-request disk read |
| NFR-03 | Unit coverage for both routers ≥ 80% (CLAUDE.md §3.5).                                                 | Coverage gate                            |
| NFR-04 | No PII is returned. The run trace exposes already-PII-masked audit metadata only; no raw request text. | Privacy (ADR-0012); §3.1                 |
| NFR-05 | Errors use the structured envelope (ADR-0076); 404/401 carry `request_id`/`trace_id`.                  | Observability/correlation                |
| NFR-06 | Config-via-env: the SLO file path is the existing `docs/sre/slo/slo.yaml`; no new required env var.    | Config                                   |

## 7. Architecture

```
GET /v1/runs/{request_id}                 (src/api/rest/routers/runs.py)
  └─ auth: Depends(get_principal)         (existing bearer JWT; read access)
  └─ request_store.get(request_id)        (RequestStoreProtocol from app.state)
       └─ None → 404 ErrorResponse (ADR-0076)
  └─ audit_logger.query_events(...)       (AuditLogger from app.state)
       └─ build timeline[] from really-associable events  (see §9.1)
  └─ RunTraceResponse{ ...state, timeline, timeline_association }

GET /v1/governance/slo-status             (src/api/rest/routers/governance.py)
  └─ auth: Depends(get_principal)
  └─ load_slo_definitions()               (cached parse of docs/sre/slo/slo.yaml)
  └─ for each SLO: observed = real in-process sample (api-gateway avail/error_rate)
                            OR { data_available: false, note: "..." }   ← §3.6 honesty
  └─ SLOStatusResponse{ source_version, services[], generated_at }
```

Both routers resolve their dependencies from `app.state` exactly as `requests.py`/`hitl.py` do
(`get_request_store`, `getattr(app.state, "audit_logger")`), so the in-memory fallbacks (no
Redis / no Postgres) keep the endpoints working in tests and local dev.

## 8. Interface Contracts _(gate: contract-driven dev)_

| Method | Path                        | Auth       | Purpose                       | Success | Errors        |
| ------ | --------------------------- | ---------- | ----------------------------- | ------- | ------------- |
| GET    | `/v1/runs/{request_id}`     | Bearer JWT | Per-request execution trace   | 200     | 401, 404, 503 |
| GET    | `/v1/governance/slo-status` | Bearer JWT | SLO targets + honest observed | 200     | 401           |

OpenAPI source of truth: `docs/api/openapi/v1/openapi.yaml` (paths + `RunTraceResponse`,
`TraceEvent`, `SLOStatusResponse`, `SLOServiceStatus`, `SLOItemStatus`, `SLOObserved` schemas; new
`runs` and `governance` tags). TS client regenerated via `make gen-api-client-ts APP=web`.

## 9. Data Model

### 9.1 Entities / payloads

**`RunTraceResponse`** (200 of `/v1/runs/{request_id}`):

| Field                  | Type                                                              | Source                                                       |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------ |
| `request_id`           | string                                                            | `RequestState.request_id`                                    |
| `status`               | string                                                            | `RequestState.status`                                        |
| `created_at`           | date-time                                                         | `RequestState.created_at`                                    |
| `updated_at`           | date-time                                                         | `RequestState.updated_at`                                    |
| `result`               | object \| null                                                    | `RequestState.result`                                        |
| `error`                | string \| null                                                    | `RequestState.error`                                         |
| `timeline`             | `TraceEvent[]`                                                    | audit events really-associated with this request (see below) |
| `timeline_association` | enum `metadata_request_id` \| `time_window_approximate` \| `none` | the strategy actually used to build `timeline`               |

**`TraceEvent`**: `{ event_type, action, outcome, risk_score?, trace_id?, occurred_at }` — taken
verbatim from a real `AuditEvent` (no synthesized events).

**Timeline association — the honest limitation (CLAUDE.md §3.6):**
The audit store is queryable by `agent_id`/`action_type`/time-window/`limit` only — it is **not
indexed by the domain `request_id`**. Investigation of the writers shows:

- `src/agents/hitl_gateway.py` writes `metadata.request_id` — but that is the **HITL request id**
  (a fresh UUID minted in the orchestrator), **not** the `RequestState.request_id` the API issued.
- `src/agents/orchestrator/orchestrator.py` writes `agent.action.proposed` with `agent_id` +
  `trace_id` and **does not** carry the domain `request_id` in metadata at all.

Therefore there is currently **no field that reliably links an `AuditEvent` back to a
`RequestState.request_id`**. Closing that gap cleanly would require writing the domain
`request_id` into audit metadata from the orchestrator/consumer — which touches the
dual-approval guardrail/HITL surface (CLAUDE.md §14) and is explicitly **out of scope** here.

The endpoint behaves honestly within that constraint, in priority order:

1. **`metadata_request_id`** — if any audit event's `metadata.request_id` exactly equals the
   requested `request_id`, the timeline is the set of those exactly-matched events. This is the
   only _exact_ path and is used whenever such events exist (it will match HITL events whose id
   happens to equal the domain id — e.g. tests, or a future writer that aligns the ids).
2. **`time_window_approximate`** — _(currently disabled by default; see Risks)_ a fallback that
   would filter by the request's `[created_at, updated_at]` window. It is **not** request-specific
   and can include unrelated concurrent activity, so the default build returns `none` rather than a
   misleading window match. The enum value is reserved so a future writer can enable it.
3. **`none`** — no event could be honestly associated; `timeline` is `[]`. This is the expected
   result for the in-memory dev/test default where no orchestrator audit events carry the domain id.

`timeline_association` always tells the caller which of the above produced the timeline, so the UI
can label an approximate or empty trace truthfully.

**`SLOStatusResponse`** (200 of `/v1/governance/slo-status`):

| Field            | Type                 | Source                         |
| ---------------- | -------------------- | ------------------------------ |
| `source_version` | string               | `slo.yaml` top-level `version` |
| `generated_at`   | date-time            | response build time            |
| `services`       | `SLOServiceStatus[]` | `slo.yaml` `services`          |

`SLOServiceStatus`: `{ name, description?, slos: SLOItemStatus[] }`.
`SLOItemStatus`: `{ name, sli_type, description?, target?, target_ms?, target_max?, window, observed: SLOObserved }`.
`SLOObserved`: `{ data_available: bool, value?: number, unit?: string, source?: string, scope?: string, note?: string }`.

- For **api-gateway / availability** and **api-gateway / error_rate**, `observed` is computed from
  the in-process `http_requests_total` counter (share of non-5xx responses), with
  `data_available: true`, `source: "prometheus:http_requests_total (in-process)"`,
  `scope: "process_lifetime"`, and a `note` that this is a process-lifetime sample, **not** the
  30-day SLO window. If the counter has zero samples, `data_available: false`.
- For **every other SLO** (latency percentiles, saturation, all agent/hitl SLOs),
  `observed.data_available` is `false` with a `note` that a metrics-query (PromQL) layer is
  required to compute it. **No number is invented.**

### 9.2 Storage key/schema convention

No new storage. Reads `RequestState` (existing keys) and `AuditEvent` (existing query API).

### 9.3 Retention

Run traces reflect whatever the request store / audit store retain (TTL per existing config). No new
retention surface.

### 9.4 Governance/response metadata

`timeline_association` and `observed.data_available`/`note`/`scope` are the explicit honesty
metadata mandated by CLAUDE.md §3.6.

## 10. Golden Signals & SLO Definitions _(gate: observability)_

| Signal     | Derivation                                | Exposed as            |
| ---------- | ----------------------------------------- | --------------------- |
| Traffic    | counted by existing `http_requests_total` | (unchanged)           |
| Latency    | endpoints are O(small) reads              | (unchanged)           |
| Error      | 401/404 via standard envelope             | `http_requests_total` |
| Saturation | no new background work                    | (unchanged)           |

This feature **adds no new SLO**; it _surfaces_ the existing `docs/sre/slo/slo.yaml` read-only.

## 11. Governance, Privacy & Security _(gate: threat & privacy review)_

| Concern                                  | Control in this spec                                                            | Maps to                        |
| ---------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------ |
| Human oversight (HITL/HOTL)              | Read-only views support oversight; no agent action taken; guardrails untouched  | ADR-0011                       |
| PII (classify L1–L4; mask at boundaries) | Returns only already-masked audit metadata + non-PII request state; no raw text | ADR-0012, §3.1                 |
| Auditability (immutable trail)           | Reads the audit trail; never writes/mutates it                                  | ADR-0026                       |
| Authn / abuse (auth, rate limit)         | Bearer JWT (`get_principal`) on both endpoints; behind existing SlowAPI limiter | specs/security/threat-model.md |
| Cost envelope                            | No LLM calls; constant-work reads                                               | ADR-0020                       |
| Pipeline security (SAST/SCA/secret/SBOM) | No new deps (PyYAML already used); ruff+mypy+bandit gates apply                 | ADR-0029                       |

STRIDE over the two untrusted inputs (`request_id` path param; bearer token): **Tampering/Info-
disclosure** — `request_id` is used only as an opaque store key / equality filter (no SQL build,
no path traversal); unknown ids 404 without leaking existence of other requests. **Spoofing** —
both endpoints require a verified JWT. **Repudiation/DoS** — read-only, bounded work, existing
rate limiter. No new `action_type`, no autonomy change → Phase 10 (AI Safety) not triggered.

## 12. Acceptance Criteria _(gate: dry-run validation)_

| ID    | Acceptance criterion (WHEN … THEN …)                                                                                                               | Covers FR(s) |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| AC-01 | WHEN a known request is GET via `/v1/runs/{id}` with a valid token, THEN 200 with its state and a `timeline` array.                                | FR-01, FR-02 |
| AC-02 | WHEN audit events carry `metadata.request_id == {id}`, THEN those events appear in `timeline` and `timeline_association == "metadata_request_id"`. | FR-02, FR-03 |
| AC-03 | WHEN no event can be associated, THEN `timeline == []` and `timeline_association == "none"`.                                                       | FR-02, FR-03 |
| AC-04 | WHEN the request_id is unknown, THEN 404 with `code == "NOT_FOUND"` (ADR-0076 envelope).                                                           | FR-04        |
| AC-05 | WHEN no bearer token is supplied to either endpoint, THEN 401 with `code == "UNAUTHORIZED"`.                                                       | FR-05        |
| AC-06 | WHEN `/v1/governance/slo-status` is GET with a valid token, THEN 200 listing every service+SLO from `slo.yaml`.                                    | FR-06        |
| AC-07 | WHEN an SLO has no computable observed value, THEN its `observed.data_available == false` with a `note`, and no fabricated number.                 | FR-07        |
| AC-08 | WHEN the api-gateway availability/error-rate counter has samples, THEN `observed.data_available == true` with `scope == "process_lifetime"`.       | FR-08        |

> **Requirement coverage footer (gate).** 8 FRs total · 8 mapped to ≥ 1 AC · **0 unmapped**.

## 13. Risks & Limitations

- **R-01 (primary):** Audit is **not indexed by domain `request_id`** and the orchestrator does not
  write it (§9.1). The exact timeline is therefore only available when a writer aligns the ids
  (e.g. HITL flows / tests). The honest mitigation is the `timeline_association` field; the full fix
  (write `request_id` into orchestrator audit metadata) is deferred because it touches §14
  dual-approval surfaces. Tracked as a follow-up.
- **R-02:** `time_window_approximate` is reserved but disabled by default to avoid presenting
  unrelated concurrent events as a request's trace (would violate §3.6's "no misleading data").
- **R-03:** SLO `observed` for api-gateway is a **process-lifetime** in-process sample, explicitly
  scoped as such — it is **not** the 30-day SLO compliance number. All other SLOs are flagged
  `data_available: false`. Real burn-rate needs a PromQL/metrics-query layer (follow-up).

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0076 (error envelope), ADR-0011 (human oversight / read views), ADR-0004
  (observability — Prometheus counters, slo.yaml).
- **Adds:** no new ADR (no new architectural decision; read-only reuse of existing patterns).
- **Produces:** two OpenAPI paths + schemas, regenerated TS client (`RunsApi`, `GovernanceApi`),
  unit tests.

## 15. Open Questions

1. Should the orchestrator/consumer be amended (separate, §14-gated change) to write the domain
   `request_id` into audit metadata so `/v1/runs/{id}` can return an _exact_ timeline? (Recommended
   follow-up; out of scope here.)
2. Is a PromQL/metrics-query integration in scope for a later iteration to fill the `observed`
   blocks with real 30-day SLO compliance? (Out of scope here.)

## 16. References

- `docs/adr/ADR-0076-api-structured-error-model-and-correlation.md`
- `docs/adr/ADR-0011-hitl-hotl-model.md`
- `docs/sre/slo/slo.yaml`
- `specs/api/SPEC-API-001-error-model-and-request-correlation.md`
- `src/agents/request_store.py`, `src/guardrails/audit_logger.py`, `src/shared/models.py`
