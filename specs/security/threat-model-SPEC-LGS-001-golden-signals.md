# Threat Model — SPEC-LGS-001 Log-Based Golden Signals (STRIDE)

**Status:** Proposed | **Owner:** Security Lead | **Last updated:** 2026-06-11
**Method:** STRIDE | **Scope:** untrusted ingestion boundary (`POST /ingestion`) + agent-facing analytics surface (`GET /analytics*`, `/audit`)
**Stack:** Java 21 / Spring Boot 3.4.5 (ADR-0066)
**ADR references:** ADR-0011 (HITL), ADR-0012 (PII masking), ADR-0019 (Redis TLS), ADR-0020 (cost/DoS), ADR-0026 (audit immutability), ADR-0066 (runtime), ADR-0067 (store), ADR-0068 (extraction/key grammar), ADR-0069 (queue)

---

## System Boundary

```
HAProxy / untrusted senders ──POST /ingestion (TLS, API-key)──▶ IngestionController
   (untrusted log batches)         │ ApiKeyFilter · RateLimiter · Bean-Validation(422)
                                    │ IpMasker (FR-02) · SignalExtractor (ADR-0068)
                                    ▼ offer() (non-blocking, bounded)
                            IngestQueue (ArrayBlockingQueue, capacity-bound — ADR-0069)
                                    ▼ take()  (virtual-thread worker)
                            AggregationWorker ──persist (TTL)──▶ Redis MetricStore (rediss://, ADR-0019/0067)
                                    ▲ query
Agentic AI Copilot / SRE ──GET /analytics* /audit (TLS, API-key)──▶ Analytics/AuditController
   (semi-trusted consumer)         │ GovernanceEvaluator → _governance + HITL flip (FR-12/13)
```

**Trust boundaries:** untrusted sender ↔ IngestionController; app ↔ Redis; app ↔ Agentic consumer
(governance-mediated); ingestion-path ↔ aggregation-worker (in-JVM queue).

---

## STRIDE Analysis

### S — Spoofing

| # | Threat                                                            | Component           | Likelihood | Impact | Controls                                                                                                   | Residual |
| - | ----------------------------------------------------------------- | ------------------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------- | -------- |
| 1 | Unauthenticated ingestion or analytics call                       | ApiKeyFilter        | High       | High   | API-key auth on `/ingestion`,`/analytics`,`/audit` (FR-10); constant-time compare; missing/invalid ⇒ 401; health exempt by design | Low      |
| 2 | Forged sender claiming to be HAProxy to inject fabricated signals  | IngestionController  | Medium     | Medium | API key scopes who may ingest; per-key audit (FR-14); poisoning impact bounded by FR-13 HITL flip (entry 13) | Low      |

### T — Tampering

| # | Threat                                                            | Component           | Likelihood | Impact   | Controls                                                                                                   | Residual |
| - | ----------------------------------------------------------------- | ------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------- | -------- |
| 3 | **Key injection** — a crafted `path` with `:`/`*`/newline/`gs:` forges or collides with another path's Redis keys | SignalExtractor / MetricStore | Medium | High | **`{path}` URL-encoded before any key assembly (ADR-0068 §4)**; `:` separators made unambiguous; identical encode on read/write; `KeyInjectionTest` (feature-spec §4.3) | Low |
| 4 | Tampered log batch in transit                                     | ingestion transport | Low        | Medium   | TLS 1.2+ to the ingestion endpoint; per-entry Bean Validation rejects type/range tampering ⇒ 422          | Low      |
| 5 | Aggregate/sample tampering at rest in Redis                       | RedisMetricStore    | Low        | Medium   | TLS (`rediss://`) + at-rest posture per ADR-0019; Redis not internet-exposed; TTL limits exposure window  | Low      |

### R — Repudiation

| # | Threat                                                            | Component           | Likelihood | Impact | Controls                                                                                                   | Residual |
| - | ----------------------------------------------------------------- | ------------------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------- | -------- |
| 6 | A caller denies an ingestion/analytics interaction                | AuditController     | Low        | High   | **Immutable audit trail** of every call: ts, endpoint, hashed key, trace id, status (FR-14, ADR-0026); `GET /audit` read-only, no delete path | Low |
| 7 | Agent denies acting on a HITL-flagged response                    | GovernanceEvaluator | Low        | Medium | `_governance.recommended_action_mode` + `human_approval_required` are response-recorded; trace id ties response to audit row | Low |

### I — Information Disclosure

| # | Threat                                                            | Component           | Likelihood | Impact   | Controls                                                                                                   | Residual |
| - | ----------------------------------------------------------------- | ------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------- | -------- |
| 8 | **Raw client IP (PII) reaches store or logs**                     | IpMasker            | Medium     | High     | IPv4 last-octet / IPv6 last-80-bit masking **before any persist or log** (FR-02, ADR-0012); `PiiLeakTest` scans store dump + logs; structured logs carry no raw `client_ip` | Low |
| 9 | API key leaked via logs/audit                                     | TraceIdFilter / AuditController | Low | High | Keys **hashed** in audit (FR-14); never logged in clear; `GlobalExceptionHandler` never echoes auth headers/body | Low |
| 10 | Error responses leak stack traces / internal paths to a caller    | GlobalExceptionHandler | Medium  | Medium   | Centralised handler returns sanitised problem bodies (422/401/429/503); no stack/PII in body              | Low      |

### D — Denial of Service

| # | Threat                                                            | Component           | Likelihood | Impact   | Controls                                                                                                   | Residual |
| - | ----------------------------------------------------------------- | ------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------- | -------- |
| 11 | **Single-node ingestion flood / unbounded growth (OOM)**          | IngestQueue / RateLimiter | Medium | High   | Per-key sliding-window rate limit ⇒ 429 + `Retry-After` (FR-11); **bounded `ArrayBlockingQueue` + non-blocking `offer()`** (ADR-0069) ⇒ drop-on-full counted as `rejected`/`gs_queue_dropped_total`, never OOM; ADR-0020 footprint bound | Medium (single-node accepted scope) |
| 12 | Oversized/expensive analytics range query exhausts CPU/Redis      | AnalyticsController  | Low        | Medium   | Required `path`; `from`/`to` range validated; TTL caps queryable history (ADR-0067); read budget per NFR-07 | Low |

### E — Elevation of Privilege

| # | Threat                                                            | Component           | Likelihood | Impact   | Controls                                                                                                   | Residual |
| - | ----------------------------------------------------------------- | ------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------- | -------- |
| 13 | **Signal poisoning → autonomous bad action** — attacker floods high-latency/error entries to drive the Agentic consumer into a harmful remediation | GovernanceEvaluator | Medium | High | **FR-13 HITL backstop**: threshold breach sets `recommended_action_mode:HITL` + `human_approval_required:true` (ADR-0011) so a human gates the action; ingestion is auth'd (entry 1) and rate-limited (entry 11); poisoning is observable via audit | Low |
| 14 | Path-traversal/enum-bypass param escalates to read foreign data   | AnalyticsController  | Low        | Medium   | `signal`/`window` constrained to enums ⇒ 422 on miss; `{path}` URL-encoded (entry 3); no path is privileged over another | Low |

---

## Summary

14 STRIDE entries across all six categories over the untrusted ingestion boundary and the
agent-facing analytics surface. Highest-priority residual is single-node ingestion DoS (entry 11),
explicitly accepted within the single-node initial scope (source-spec §3, §15-Q2) and mitigated by
rate limiting + bounded-queue backpressure; the Kafka scale-out path (ADR-0069) is the recorded exit.
The key-injection (entry 3), PII-leak (entry 8) and signal-poisoning→HITL (entry 12) threats are the
security drivers behind ADR-0068's URL-encoding rule, ADR-0012's masking, and FR-13's HITL backstop
respectively — each with a named abuse-case test in feature-spec §4.3.
