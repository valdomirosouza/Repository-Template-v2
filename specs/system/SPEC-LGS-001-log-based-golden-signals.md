---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /project and CI read this block)
# Reuse: copy this file, change the id/title/owner and rewrite each section.
# Keep the section skeleton; it maps 1:1 onto the 15-phase Agentic SDLC.
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-LGS-001
title: Log-Based Golden Signals — Ingestion & Predictive Analytics Infrastructure
version: 0.1.0
status: draft                      # draft | in-review | approved | implemented | superseded
owner: valdomirosouza
created: 2026-06-07
source: >-
  Academic article + presentation "Log-Based Golden Signals: A Scalable
  Ingestion and Predictive Analytics Infrastructure for Agentic AI Copilots"
  (V. de O. Souza Jr., PPGCA/Unisinos, 2026).
deployment_topology: monorepo-services    # monorepo-services | standalone-repo  (see §1.4)
governing_adrs: [ADR-0003, ADR-0011, ADR-0012, ADR-0020, ADR-0026, ADR-0029]
new_adrs_required: [redis-as-timeseries-store, golden-signal-extraction-rules]
related_specs: [specs/ai/, specs/privacy/, specs/security/threat-model.md]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-LGS-001 — Log-Based Golden Signals

> **One-line scope.** A governed, containerised pipeline that ingests HAProxy
> access logs, extracts the four Golden Signals per request path, aggregates them
> into time windows, and exposes latency percentiles (P50/P95/P99) over a REST
> API — forming the **data foundation** an Agentic AI Copilot consumes to reduce
> MTTD/MTTR under HITL/HOTL governance.

<!-- TEMPLATE NOTE: every numbered section below is mandatory. Sections marked
     (gate) are checked by a phase gate in specs/sdlc/. Do not delete headings;
     write "N/A — <reason>" if a section genuinely does not apply. -->

---

## 1. Context & Problem

### 1.1 Problem statement
Modern distributed systems emit observability data faster than humans can triage,
so anomaly detection and remediation lag. Existing AIOps tooling correlates alerts
but does not provide a predictive, query-able **data foundation** that an
autonomous agent can reason over. Latency averages also hide tail behaviour that
drives real user impact.

### 1.2 Research / product question
How can a scalable HAProxy log ingestion and predictive-analytics pipeline,
organised around Golden Signals, provide the statistical foundation for an
Agentic AI Copilot that lowers Mean Time to Detection (MTTD) and Mean Time to
Recovery (MTTR) during incident response — while remaining auditable and governed?

### 1.3 Why now / motivation
This pipeline is the data-layer prerequisite of the broader master's research
("Agentic AI as a copilot to reduce MTTD/MTTR"). The agent itself is **out of
scope here**; this spec delivers only the foundation it will consume.

### 1.4 Deployment topology decision  *(decide before Phase 1)*
This feature maps to **four services + two infra dependencies**, which fits the
monorepo's `services/` catalog and `services.yaml`. Default: `monorepo-services`
(register each service, reuse the repo's CI/CD, observability and governance).
Alternative `standalone-repo` (generate a fresh repo from the template) is valid
for a throwaway research artifact but loses the shared 15-phase guarantees.
**State the chosen value in the metadata header.**

---

## 2. Goals & Success Metrics

| ID   | Goal | Measure of success |
|------|------|--------------------|
| G-01 | Real-time Golden Signal availability | P50/P95/P99 per path queryable within one aggregation window of ingestion |
| G-02 | Tail-latency visibility | P95 and P99 exposed, not just mean — per path & signal |
| G-03 | Privacy-safe by construction | No raw client IP reaches storage or logs (masked at ingestion) |
| G-04 | Auditability for agentic consumption | Every ingestion/analytics call recorded in an immutable audit trail |
| G-05 | Governed autonomy hooks | Responses carry HITL/HOTL guidance the agent layer can act on |

<!-- TEMPLATE NOTE: goals must be measurable. If you cannot state a measure, it is
     a non-goal or an open question, not a goal. -->

---

## 3. Non-Goals / Out of Scope

- The Agentic AI Copilot, its planner, or any LLM inference (consumes this; not built here).
- Anomaly-detection / forecasting models over the time series (future work).
- Distributed tracing ingestion (future — this spec is logs → Golden Signals only).
- Long-horizon historical storage (Redis-only by design; see §13 limitation).
- Production multi-tenant scaling, HA Redis clustering (initial scope is single-node).

---

## 4. Consumers & Personas

| Consumer | Need from this system |
|----------|-----------------------|
| Agentic AI Copilot (primary) | `GET /analytics` percentiles + governance metadata for predictive reasoning |
| SRE / NOC engineer | Same percentiles for manual incident triage; audit trail for post-incident review |
| Platform / governance owner | Evidence that PII masking, auth, audit and HITL controls are enforced |

---

## 5. Functional Requirements

<!-- TEMPLATE NOTE: one testable statement per row. Each FR must trace to an
     acceptance criterion in §12 and (where relevant) a Golden Signal in §10. -->

| ID    | Requirement |
|-------|-------------|
| FR-01 | Accept HAProxy log batches via `POST /ingestion` (JSON array), validating each entry against a published schema; reject malformed batches with `422`. |
| FR-02 | Mask client IPs **before** any field is persisted or logged (IPv4 last octet; IPv6 last 80 bits). |
| FR-03 | Extract the four Golden Signals per `(path, window)` from each entry (see §10). |
| FR-04 | Publish validated, signal-extracted events to an internal queue, decoupling ingestion from processing. |
| FR-05 | A worker aggregates queued events into **1-minute and 5-minute** windows, computing `count, sum, min, max, histogram` per `(path, signal, window)`. |
| FR-06 | Persist aggregates to the time-series store with a configurable retention policy (default `1m:2h`, `5m:24h`). |
| FR-07 | Serve `GET /analytics?path=&signal=&window=&from=&to=` returning P50/P95/P99 per bucket plus a summary; percentiles computed by rank-based interpolation over the store (no external stats lib). |
| FR-08 | Serve `GET /analytics/paths` listing all currently tracked paths. |
| FR-09 | Serve health endpoints reporting store connectivity and tracked-path count. |
| FR-10 | Enforce API-key auth on ingestion and analytics (not on health); return `401` when missing/invalid. |
| FR-11 | Rate-limit `POST /ingestion` per key (sliding window); return `429` + `Retry-After` when exceeded. |
| FR-12 | Attach a `_governance` block to analytics responses (data classification, pii_sanitized, retention, audit pointer, recommended_action_mode, human_approval_required). |
| FR-13 | When thresholds breach (e.g. P99 latency or error rate over limit), set `recommended_action_mode: HITL` and `human_approval_required: true`. |
| FR-14 | Append every ingestion/analytics call to an immutable audit trail (timestamp, endpoint, hashed key, trace id, status); expose `GET /audit?limit=`. |

---

## 6. Non-Functional Requirements

| ID     | Requirement |
|--------|-------------|
| NFR-01 | All services containerised and orchestrated via Docker Compose on a shared network. |
| NFR-02 | Python asyncio-native throughout (FastAPI for APIs, async worker). Pin Python to the repo's supported runtime. |
| NFR-03 | Structured JSON logging on every service; propagate a trace id (`X-Trace-Id`, generated if absent). |
| NFR-04 | All configuration via environment variables with documented defaults (`.env.example`). |
| NFR-05 | Unit-test coverage ≥ 80% on core business logic (percentiles, masking, extraction); integration test for the full pipeline. |
| NFR-06 | Every store access handles connection/timeout errors explicitly; no hidden global state (use lifespan context). |
| NFR-07 | Real-time read performance suitable for incident-time queries (document the latency budget for `GET /analytics`). |
| NFR-08 | Dependency versions pinned (no ranges); `dependency-manifest.yaml` + SBOM produced (per documentation-standards). |

---

## 7. Architecture

Four sequential components across three functional layers (ingestion → processing
→ query), event-decoupled by an internal queue.

```
HAProxy instances ──POST /ingestion (JSON batch)──▶ Ingestion API
        (log source)                                 │ validate · mask PII · extract signals
                                                      ▼ publish
                                              [ internal queue ]
                                                      ▼ consume
                                              Metrics Processor (async worker)
                                                      │ aggregate 1m/5m · count/sum/min/max/hist
                                                      ▼ persist
                                              Time-Series Store (Redis)
                                                      │ retention 1m:2h / 5m:24h
                                                      ▼ GET /analytics
                                              Analytics API  ──▶ consumed by Agentic layer
                                                P50/P95/P99 · error rate · traffic · saturation %
```

Component responsibilities, ports and tech are enumerated in §8 and §9. The queue
choice (in-process vs Redis stream vs broker) is an architecture-phase decision —
align it with **ADR-0003 (async strategy)** and record any deviation as a new ADR.

---

## 8. Interface Contracts  *(gate: contract-driven dev)*

<!-- TEMPLATE NOTE: this section is the source for the OpenAPI spec in docs/api/.
     Never hand-write stubs — generate from the contract. -->

| Method | Path | Auth | Purpose | Success | Errors |
|--------|------|------|---------|---------|--------|
| POST | `/ingestion` | API key | Submit a log batch | `202` accepted (counts) | `401`, `422`, `429` |
| GET  | `/analytics` | API key | Percentiles per path & signal | `200` buckets + summary + `_governance` | `401`, `422` |
| GET  | `/analytics/paths` | API key | List tracked paths | `200` array | `401` |
| GET  | `/analytics/health` | none | Liveness + store status | `200` `{status, redis_connected, tracked_paths}` | `503` |
| GET  | `/audit` | API key | Last N audit entries | `200` array | `401` |

**Query params for `/analytics`:** `path` (required), `signal` ∈ {traffic,latency,error,saturation},
`window` ∈ {1m,5m}, `from`/`to` (ISO-8601, optional).

---

## 9. Data Model

### 9.1 Inbound log entry (validated at ingestion)
Fields: `timestamp` (ISO-8601), `path`, `method`, `status_code` (int),
`response_time_ms` (float), `bytes_sent` (int), `client_ip` (masked on entry),
`backend_name` (optional).

### 9.2 Store key convention  *(define once; processor and analytics must agree)*
Document the exact key scheme during the data-model phase, e.g.
`gs:{signal}:{path}:{window}:{epoch_bucket}` for aggregates and a sorted set for
latency samples used in percentile interpolation. Pin it in an ADR or this spec so
both services read/write identically.

### 9.3 Retention
Configurable per window; defaults `1m → 2h`, `5m → 24h`. Note the historical-depth
limitation in §13.

### 9.4 `_governance` response block
`{ data_classification, pii_sanitized, retention_policy, audit_trail,
recommended_action_mode (HITL|HOTL), human_approval_required }`.

---

## 10. Golden Signals & SLO Definitions  *(gate: observability)*

| Signal | Derivation from a log entry | Exposed as |
|--------|------------------------------|-----------|
| Traffic | Request count per `(path, window)` | count per bucket |
| Latency | `response_time_ms` into a per-window histogram | P50 / P95 / P99 per bucket |
| Error | Flag when `status_code >= 400` | error_rate = errors / total |
| Saturation | Proxy from `bytes_sent` vs configurable threshold | saturation_pct |

Percentile rationale: averages hide tail latency; P95/P99 are the SLO-relevant
indicators for critical services (tail-at-scale). Define this system's own SLOs in
`docs/sre/slo/slo.yaml` (e.g. availability of `/analytics`, freshness lag of
aggregates) and the threshold values in FR-13 that flip a response to HITL.

---

## 11. Governance, Privacy & Security  *(gate: threat & privacy review)*

| Concern | Control in this spec | Maps to |
|---------|----------------------|---------|
| Human oversight | HITL before critical agent actions; HOTL = autonomous + continuous audit | ADR-0011 |
| PII | IP masking before storage/logging; classify telemetry L-level | ADR-0012, specs/privacy/ |
| Auditability | Immutable audit trail of every API call; traceable by trace id | ADR-0026 |
| Authn / abuse | API-key auth + rate limiting | specs/security/threat-model.md |
| Cost | Bound queue/worker/Redis footprint; document cost envelope | ADR-0020 |
| Pipeline security | SAST/SCA/secret-scan/SBOM in CI | ADR-0029 |

**New ADRs to author during the ADR-alignment phase:**
`ADR-xxxx Redis as time-series store` (record the retention trade-off and the
InfluxDB/TimescaleDB exit path), and `ADR-xxxx Golden-Signal extraction rules`
(saturation proxy definition, window boundaries).

Run a STRIDE pass over the ingestion boundary (untrusted log batches) and the
agent-facing analytics surface.

---

## 12. Acceptance Criteria  *(gate: dry-run validation)*

<!-- TEMPLATE NOTE: phrase each as observable and runnable. These become the
     dry-run evidence in the /project FINAL-REPORT. -->

| ID    | Acceptance criterion |
|-------|----------------------|
| AC-01 | `docker compose ps` shows all services healthy; store responds to a ping. |
| AC-02 | A malformed batch is rejected `422`; a valid batch returns `202` with accepted/rejected counts. |
| AC-03 | After ingesting a sample with known IPs, no unmasked IP appears in the store or logs. |
| AC-04 | After seeding ~1k synthetic entries across ≥5 paths, `GET /analytics?...&signal=latency&window=1m` returns non-empty numeric P50/P95/P99. |
| AC-05 | `GET /analytics/paths` lists every seeded path. |
| AC-06 | Percentile correctness verified against a known dataset (unit test). |
| AC-07 | Unauthenticated calls return `401`; exceeding the rate limit returns `429`. |
| AC-08 | Seeding high-latency data flips `recommended_action_mode` to `HITL` and `human_approval_required` to `true`. |
| AC-09 | `GET /audit?limit=N` returns the last N interactions with hashed keys. |
| AC-10 | Full pipeline integration test (seed → process → query) exits `0`; error rate within ±2% of injected rate. |

---

## 13. Risks & Limitations

- **Redis retention horizon.** Redis as the sole store limits long-horizon analysis
  under high path cardinality. Documented exit path: dedicated TSDB (InfluxDB /
  TimescaleDB). Record as an explicit ADR consequence, not a silent assumption.
- **Saturation as a `bytes_sent` proxy** is approximate; flag where it diverges
  from true resource saturation.
- **Window boundaries** can split bursty traffic; document the chosen boundary
  semantics so percentiles are reproducible.

---

## 14. ADR & Dependency Impact

- Reuses: ADR-0003 (async), ADR-0011 (HITL/HOTL), ADR-0012 (PII), ADR-0020 (cost),
  ADR-0026 (audit immutability), ADR-0029 (DevSecOps).
- Adds: the two new ADRs in §11.
- Produces: `dependency-manifest.yaml`, pinned lockfiles, SBOM, OpenAPI spec,
  README, runbook stub, `slo.yaml` (per documentation-standards).

---

## 15. Open Questions

<!-- Anything that must be resolved at a HITL gate rather than assumed. -->
1. Queue implementation: in-process asyncio queue, Redis stream, or external broker?
2. Single-node Redis acceptable for initial scope, or is HA required from day one?
3. Exact saturation threshold + unit, and whether it is per-path or global.
4. Topology: register in this monorepo's `services.yaml`, or generate a standalone repo? (see §1.4)

---

## 16. References
- Adabara, I. et al. *Trustworthy agentic AI systems.* F1000Research 14:905, 2025.
- Acharya, D. B. et al. *Agentic AI: Autonomous Intelligence for Complex Goals.* IEEE Access 13, 2025.
- Diaz-de-Arcaya, J. et al. *Challenges, Opportunities, and Roadmap of MLOps and AIOps.* ACM Computing Surveys 56(4), 2024.
- Beyer, B. et al. *Site Reliability Engineering.* O'Reilly, 2016.
- Dean, J.; Barroso, L. A. *The tail at scale.* Communications of the ACM 56(2), 2013.
```
