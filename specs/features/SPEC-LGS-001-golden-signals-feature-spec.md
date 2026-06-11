# Feature Spec — SPEC-LGS-001 Log-Based Golden Signals (Java 21 / Spring Boot 3.4.5)

**Status:** draft (Phase 4 — Specification, CONTROL) | **Owner:** valdomirosouza
**Source spec:** `specs/system/SPEC-LGS-001-log-based-golden-signals.md`
**Runtime stack:** Java 21 / Spring Boot 3.4.5 (per **ADR-0066**; spec-conformant, not a deviation)
**Tier:** GOVERNED | **Backlog:** BL-05 (Specification), BL-06 (Architecture)
**Governing ADRs:** ADR-0003 (async), ADR-0011 (HITL/HOTL), ADR-0012 (PII), ADR-0020 (cost),
ADR-0026 (audit immutability), ADR-0066 (runtime stack), **ADR-0067/0068/0069** (drafted this delivery)

> This feature spec elaborates the 14 FRs + 8 NFRs of SPEC-LGS-001 into a concrete,
> implementable Java/Spring Boot design. It is the contract the Phase-6 build depends on:
> every component, interface, key, threshold, edge case and test below is intended to leave
> **no ambiguity** for the implementer. Where it resolves an open question from the source
> spec §15, it defers to the matching ADR (0067/0068/0069).

---

## 0. Service topology (monorepo-services)

Per the source spec §1.4 the feature is one logical pipeline. For the GOVERNED Java build it is
delivered as **one Spring Boot service** `services/golden-signals` (single deployable, internal
component layering) rather than four micro-deployables — this honours NFR-01 (containerised) and
ADR-0020 (bound the cost/operational envelope: one JVM, one Redis, one Compose unit) while keeping
the four logical components (§7 of the source spec) as in-JVM modules decoupled by the bounded
queue of ADR-0069. Register `golden-signals` in `services.yaml` + `.github/CODEOWNERS` at build time
(Phase 6); scaffold with `make new-service NAME=golden-signals LANG=java`.

Package root: `com.yourorg.goldensignals` (matches the repo convention `com.yourorg.<service>`
observed in `services/domain-service`), with `api` / `domain` / `infra` sub-packages.

---

## 1. Component breakdown

```
HAProxy ─POST /ingestion─▶ IngestionController (api)
                              │ 1. auth (ApiKeyFilter)  2. rate-limit (RateLimiter)
                              │ 3. schema-validate (Bean Validation → 422)
                              │ 4. IpMasker.mask()  5. SignalExtractor.extract()
                              ▼ offer()
                         IngestQueue  (ArrayBlockingQueue<SignalEvent>, bounded — ADR-0069)
                              ▼ take()  (virtual-thread worker — Java 21 Loom)
                         AggregationWorker (domain)
                              │ window-bucket (1m & 5m, epoch-aligned LEFT-closed/RIGHT-open — ADR-0068)
                              │ count/sum/min/max + per-window latency-sample sorted set
                              ▼ persist (TTL retention — ADR-0067)
                         MetricStore (interface)
                            ├─ InMemoryMetricStore (tests, default-profile)
                            └─ RedisMetricStore     (prod-profile — ADR-0067)
                              ▲ read
                         AnalyticsController (api) ─GET /analytics─▶ Agentic layer
                              │ PercentileCalculator (rank interpolation — no external stats lib)
                              │ GovernanceDecorator (_governance block, HITL flip — FR-12/13)
```

### 1.1 `api` layer (Spring Web MVC, virtual-thread request executor)

| Component               | Type                       | Responsibility                                                                                   |
| ----------------------- | -------------------------- | ------------------------------------------------------------------------------------------------ |
| `IngestionController`   | `@RestController`          | `POST /ingestion`; binds `List<LogEntryDto>`, returns `202 {accepted, rejected}` (FR-01)         |
| `AnalyticsController`   | `@RestController`          | `GET /analytics`, `/analytics/paths`, `/analytics/health` (FR-07/08/09)                          |
| `AuditController`       | `@RestController`          | `GET /audit?limit=N` (FR-14)                                                                      |
| `ApiKeyFilter`          | `OncePerRequestFilter`     | API-key auth on `/ingestion`,`/analytics`,`/audit`; **not** on `/analytics/health` → 401 (FR-10) |
| `RateLimiter`           | filter / `HandlerInterceptor` | Sliding-window per hashed key on `POST /ingestion` → 429 + `Retry-After` (FR-11)             |
| `TraceIdFilter`         | `OncePerRequestFilter`     | Read/generate `X-Trace-Id`, put in MDC for JSON logs (NFR-03)                                     |
| `GlobalExceptionHandler`| `@RestControllerAdvice`    | Maps validation→422, auth→401, rate→429, store-down→503; never leaks PII/stack to body            |

Enable Loom for request handling: `spring.threads.virtual.enabled=true` (Spring Boot 3.4.5).

### 1.2 `domain` layer (pure, unit-testable, no Spring)

| Component               | Responsibility                                                                                       |
| ----------------------- | ---------------------------------------------------------------------------------------------------- |
| `IpMasker`              | IPv4 → zero last octet; IPv6 → zero last 80 bits (last 5 hextets). Pure function (FR-02)              |
| `SignalExtractor`       | `LogEntry → SignalEvent` for the 4 signals per `(path, window)` (FR-03, ADR-0068)                      |
| `WindowBucketer`        | epoch-align a timestamp to the 1m/5m bucket start; LEFT-closed/RIGHT-open (ADR-0068)                   |
| `Aggregate`             | mutable accumulator: `count, sum, min, max, errors, samples (TreeMap/sorted)` per `(path,signal,win)` |
| `PercentileCalculator`  | rank-based linear interpolation P50/P95/P99 over a sorted sample set (FR-07, AC-06)                    |
| `GovernanceEvaluator`   | applies FR-13 thresholds → `recommended_action_mode`, `human_approval_required` (FR-12/13)             |
| `SignalEvent` / `LogEntry` / `Bucket` | immutable records (Java 21 `record`)                                                    |

### 1.3 queue + worker (ADR-0069)

| Component            | Responsibility                                                                                  |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| `IngestQueue`        | `ArrayBlockingQueue<SignalEvent>` capacity `INGEST_QUEUE_CAPACITY` (default 10000). `offer()` non-blocking; on full → increment `gs_queue_dropped_total`, ingestion still returns 202 with `rejected` count for dropped (FR-04, ADR-0020 backpressure) |
| `AggregationWorker`  | single virtual-thread (`Executors.newVirtualThreadPerTaskExecutor()` running a `take()` loop) draining the queue into `Aggregate`s; flushes to `MetricStore` on window roll-over and on a periodic timer (FR-05) |

### 1.4 `infra` / store (ADR-0067)

`MetricStore` interface (read+write) with two implementations selected by Spring profile:
`InMemoryMetricStore` (`@Profile("!redis")`, tests + local) and `RedisMetricStore`
(`@Profile("redis")`, prod — Lettuce client). TTL retention per window (ADR-0067). Key grammar,
sorted-set sample storage and URL-encoding of `{path}` are fixed in **ADR-0068**.

```java
public interface MetricStore {
    void persist(Bucket bucket);                                  // upsert aggregate + samples
    List<Bucket> query(String path, Signal signal, Window window,
                       Instant from, Instant to);                 // FR-07
    Set<String> trackedPaths();                                   // FR-08
    boolean ping();                                               // FR-09 health
}
```

---

## 2. Interface contracts (binding — implementer must not vary)

Identical to source-spec §8. Concrete bodies:

- `POST /ingestion` → `202 {"accepted": <int>, "rejected": <int>}`; per-entry validation failures
  count toward `rejected` (batch not rejected wholesale unless the JSON itself is malformed → 422).
- `GET /analytics?path=&signal=&window=&from=&to=` → `200 {buckets:[{bucket_start, p50, p95, p99,
  count, error_rate, saturation_pct}], summary:{...}, _governance:{...}}`. `path` required; missing
  required param → 422. `signal ∈ {traffic,latency,error,saturation}`, `window ∈ {1m,5m}`.
- `GET /analytics/paths` → `200 ["/a","/b"]`.
- `GET /analytics/health` → `200 {status, redis_connected, tracked_paths}` (or `503` if store down).
- `GET /audit?limit=N` → `200 [{ts, endpoint, hashed_key, trace_id, status}]`.

`_governance` block (FR-12): `{data_classification:"telemetry-L2", pii_sanitized:true,
retention_policy:"1m:2h,5m:24h", audit_trail:"/audit", recommended_action_mode:"HOTL"|"HITL",
human_approval_required:boolean}`.

---

## 3. Configuration (NFR-04 — env vars + documented defaults)

| Env var                       | Default     | Meaning                                                        |
| ----------------------------- | ----------- | -------------------------------------------------------------- |
| `GS_API_KEYS`                 | _(required)_| comma-separated valid API keys (compared constant-time)        |
| `INGEST_QUEUE_CAPACITY`       | `10000`     | bounded queue size (ADR-0069)                                  |
| `SATURATION_BYTES_THRESHOLD`  | `1048576`   | 1 MiB; `bytes_sent >=` ⇒ saturated sample (ADR-0068)          |
| `RETENTION_1M_SECONDS`        | `7200`      | 1m-window TTL = 2h (ADR-0067)                                 |
| `RETENTION_5M_SECONDS`        | `86400`     | 5m-window TTL = 24h (ADR-0067)                               |
| `RATE_LIMIT_PER_MINUTE`       | `600`       | per-key sliding-window ingestion cap (FR-11)                  |
| `HITL_P99_LATENCY_MS`         | `1000`      | P99 over this ⇒ HITL flip (FR-13)                            |
| `HITL_ERROR_RATE`             | `0.05`      | error_rate over this ⇒ HITL flip (FR-13)                     |
| `SPRING_PROFILES_ACTIVE`      | `(none)`    | set `redis` for `RedisMetricStore`; default = in-memory       |
| `SATURATION_BYTES_THRESHOLD__<path>` | —    | optional per-path override (ADR-0068)                         |

---

## 4. Test strategy (NFR-05 — ≥80% on core logic; AC-02/03/04/06/07/08/10)

### 4.1 Unit (JUnit 5, no Spring context — `domain` layer)

| Test class                       | Asserts                                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------------------------ |
| `PercentileCalculatorTest`       | Rank-interpolation P50/P95/P99 against a **known dataset** (AC-06); linear interpolation between ranks; documented method matches FR-07 |
| `IpMaskerTest`                   | IPv4 `203.0.113.42 → 203.0.113.0`; IPv6 `2001:db8:1:2:3:4:5:6 → 2001:db8:1:0:0:0:0:0`; idempotent; already-masked passthrough; malformed IP → masked-or-rejected, never persisted raw (FR-02, AC-03) |
| `SignalExtractorTest`            | traffic=+1; error flagged iff `status_code>=400`; saturation iff `bytes_sent>=threshold` incl. per-path override; latency sample = `response_time_ms` (ADR-0068) |
| `WindowBucketerTest`             | epoch alignment for 1m & 5m; LEFT-closed/RIGHT-open boundary; a sample at exactly the bucket end lands in the **next** bucket (ADR-0068) |
| `GovernanceEvaluatorTest`        | P99 > `HITL_P99_LATENCY_MS` ⇒ HITL+approval; error_rate > `HITL_ERROR_RATE` ⇒ HITL; otherwise HOTL (FR-13, AC-08) |
| `AggregateTest`                  | count/sum/min/max correct; error count; sample set ordering                                       |

### 4.2 Integration (`@SpringBootTest`, in-memory store profile; Testcontainers-Redis for the redis profile)

| Test                             | Asserts                                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------------------------ |
| `PipelineIntegrationTest`        | seed→process→query: ingest ~1k synthetic entries over ≥5 paths, await worker drain, `GET /analytics?signal=latency&window=1m` returns non-empty numeric P50/P95/P99; error rate within ±2% of injected (AC-04, AC-10) |
| `PathsIntegrationTest`           | `/analytics/paths` lists every seeded path (AC-05)                                                |
| `HealthIntegrationTest`          | `/analytics/health` 200 with `redis_connected` + `tracked_paths`; store-down ⇒ 503 (AC-01)       |
| `RedisStoreContractTest`         | `RedisMetricStore` vs `InMemoryMetricStore` produce identical query results for the same seed (ADR-0067 interface parity); TTL set per window |

### 4.3 Security / abuse (markers parallel `tests/abuse_cases/`, CLAUDE.md §3.2)

| Test                             | Asserts                                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------------------------ |
| `MalformedBatchTest`             | non-array / wrong-typed / missing-required JSON ⇒ 422, nothing persisted (FR-01, AC-02)          |
| `KeyInjectionTest`               | a `path` containing `:` / `*` / newline / `gs:` prefix cannot collide with or read another path's keys — `{path}` is URL-encoded before key assembly (ADR-0068) |
| `AuthTest`                       | missing key ⇒ 401; invalid key ⇒ 401; health needs no key (FR-10, AC-07)                         |
| `RateLimitTest`                  | exceeding `RATE_LIMIT_PER_MINUTE` ⇒ 429 + `Retry-After` (FR-11, AC-07)                            |
| `PiiLeakTest`                    | after ingesting known IPs, scan store dump + captured logs: no unmasked octet/hextet present (FR-02, AC-03) |
| `SignalPoisoningTest`            | a flood of high-latency entries flips governance to HITL rather than silently auto-acting (FR-13 backstop) |

---

## 5. Edge-case catalogue (binding — each maps to a unit test above)

| # | Edge case                       | Required behaviour                                                                              |
| - | ------------------------------- | ---------------------------------------------------------------------------------------------- |
| E1| **Empty bucket** (no samples)   | `query` omits the bucket; `/analytics` returns `[]` buckets + summary with nulls, not an error |
| E2| **Single-sample percentile**    | P50=P95=P99=that sample (rank interpolation degenerates to the one value) — no div-by-zero      |
| E3| **Window boundary sample**      | timestamp == bucket end belongs to the **next** bucket (LEFT-closed/RIGHT-open, ADR-0068)       |
| E4| **IPv6 masking**                | last 80 bits zeroed (last 5 hextets); compressed `::` forms normalised before masking           |
| E5| **HITL threshold flip**         | exactly-at-threshold is **not** a flip (`>` strict); one tick over flips and sets approval=true |
| E6| **Queue full**                  | `offer()` fails ⇒ event counted as `rejected`, `gs_queue_dropped_total++`, ingestion still 202 |
| E7| **Two-window double-count**     | one entry updates both its 1m and 5m bucket exactly once each (no cross-window leakage)         |
| E8| **Unknown signal/window param** | `signal`/`window` outside the enum ⇒ 422 (not 500)                                              |

---

## 6. Traceability matrix (FR/AC → component → test)

| FR    | Component(s)                          | AC        | Test                         |
| ----- | ------------------------------------- | --------- | ---------------------------- |
| FR-01 | IngestionController, GlobalExceptionHandler | AC-02 | MalformedBatchTest           |
| FR-02 | IpMasker                              | AC-03     | IpMaskerTest, PiiLeakTest    |
| FR-03 | SignalExtractor                       | AC-06     | SignalExtractorTest          |
| FR-04 | IngestQueue                           | —         | PipelineIntegrationTest      |
| FR-05 | AggregationWorker, WindowBucketer     | AC-04     | WindowBucketerTest, PipelineIntegrationTest |
| FR-06 | MetricStore (TTL)                     | —         | RedisStoreContractTest       |
| FR-07 | AnalyticsController, PercentileCalculator | AC-04/06 | PercentileCalculatorTest    |
| FR-08 | AnalyticsController                   | AC-05     | PathsIntegrationTest         |
| FR-09 | AnalyticsController                   | AC-01     | HealthIntegrationTest        |
| FR-10 | ApiKeyFilter                          | AC-07     | AuthTest                     |
| FR-11 | RateLimiter                           | AC-07     | RateLimitTest                |
| FR-12 | GovernanceEvaluator                   | —         | GovernanceEvaluatorTest      |
| FR-13 | GovernanceEvaluator                   | AC-08     | GovernanceEvaluatorTest, SignalPoisoningTest |
| FR-14 | AuditController, audit store          | AC-09     | (audit integration test)     |

All 14 FRs and all 10 ACs are covered. NFR-02 (Java 21 virtual threads) is satisfied by the
ADR-0069 worker; NFR-05 coverage gate is the Phase-6/8 enforcement point.

## 7. Open questions resolved by this delivery

- §15-Q1 (queue impl) → **ADR-0069** (in-JVM `ArrayBlockingQueue` + virtual-thread worker).
- §15-Q3 (saturation threshold + scope) → **ADR-0068** (1 MiB default, per-path env override).
- §15-Q2 (single-node Redis) → accepted for initial scope (source spec §3 non-goal); **ADR-0067**.
- §15-Q4 (topology) → monorepo-services, one `services/golden-signals` deployable (§0 above).

No new `SPEC_DEVIATION` introduced — the Java stack is already reconciled by ADR-0066.
