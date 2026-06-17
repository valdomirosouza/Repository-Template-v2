# ADR-0067 — Redis as the Golden-Signals Time-Series Store

**Status:** Proposed
**Date:** 2026-06-11
**Authors:** Valdomiro Souza
**Reviewers:** Tech Lead
**Relates to:** [ADR-0066](ADR-0066-spec-lgs-001-runtime-stack-java-spring-boot.md) (Java runtime), [ADR-0020](ADR-0020-cost-governance.md) (cost), [ADR-0019](ADR-0019-redis-tls-encryption.md) (Redis TLS), [ADR-0068](ADR-0068-golden-signal-extraction-rules.md) (key grammar)
**Scope:** `SPEC-LGS-001` (Log-Based Golden Signals) only — resolves source-spec §13 (Redis retention horizon) and §15-Q2 (single-node Redis).

---

## Context

`SPEC-LGS-001` aggregates HAProxy-derived Golden Signals into 1-minute and 5-minute windows and
must serve P50/P95/P99 percentiles per `(path, signal, window)` at incident time (FR-06, FR-07,
NFR-07). The store must: hold short-horizon time-series aggregates **and** the raw latency sample
sets needed for rank-based percentile interpolation (FR-07 forbids an external stats library);
expire data automatically per the retention policy (`1m:2h`, `5m:24h` — FR-06); answer range
queries fast enough for incident triage (NFR-07); and not introduce a heavy new operational
surface (ADR-0020 cost envelope, single-node initial scope per source-spec §3 / §15-Q2).

The source spec (§11, §13, §14) explicitly calls for a `Redis as time-series store` ADR that
records the retention trade-off and the InfluxDB/TimescaleDB exit path. This is that decision.

## Decision

**Use single-node Redis as the time-series store for `SPEC-LGS-001`, behind a `MetricStore`
interface with an in-memory implementation for tests and a Redis implementation for prod.**

1. **`MetricStore` abstraction.** All read/write goes through a Java `MetricStore` interface
   (`persist`, `query`, `trackedPaths`, `ping`). Two Spring-profile-selected implementations:
   - `InMemoryMetricStore` (`@Profile("!redis")`) — default for unit/integration tests and local
     dev; deterministic, no infra. This is what keeps NFR-05's core-logic tests Redis-free.
   - `RedisMetricStore` (`@Profile("redis")`) — production, Lettuce client. TLS (`rediss://`) and
     at-rest expectations per ADR-0019.
     This abstraction is the seam the InfluxDB/TimescaleDB exit path plugs into (a third
     implementation), so no caller changes when the backend changes.

2. **Data layout** (key grammar, sorted-set sample storage and `{path}` URL-encoding are fixed in
   **ADR-0068**, which this ADR references rather than re-specifies): per-`(path,signal,window,
epoch_bucket)` aggregate fields in a Redis hash, plus a per-bucket **sorted set** of latency
   samples used by `PercentileCalculator` for rank interpolation, plus a `gs:paths` set for FR-08.

3. **Retention via native TTL.** Every key is written with `EXPIRE` from config:
   - `RETENTION_1M_SECONDS` default `7200` (2h) for 1m-window keys,
   - `RETENTION_5M_SECONDS` default `86400` (24h) for 5m-window keys.
     Retention is therefore enforced by Redis itself — no sweep job, no cron, bounding memory (ADR-0020).

4. **Single-node, initial scope.** HA Redis clustering is a documented non-goal (source-spec §3,
   §15-Q2). The store-down path is explicit: `MetricStore.ping()` false ⇒ `/analytics/health` 503,
   `redis_connected:false` (NFR-06: every store access handles connection/timeout errors explicitly).

5. **Dedicated, ephemeral, internal-only instance — not the shared dev Redis.** The `SPEC-LGS-001`
   store is a _separate_ Redis from the shared development `redis` in `docker-compose.yml` (which is
   host-published on `6379` and persistent via `--save 60 1` + the `redis_data` volume). Because the
   golden-signals store holds only short-horizon TTL telemetry (point 3) that is re-derivable from
   logs, it runs **profile-scoped and internal-only** (no host port publish) with **persistence
   disabled** (`--save "" --appendonly no`, no data volume). Reusing the shared persistent Redis is
   explicitly rejected: it would couple unrelated workloads onto one instance, expose a second Redis
   on the host, and persist ephemeral telemetry past its TTL horizon — making the "no durability
   guarantee" trade-off below accidental rather than intentional. (This records the topology
   decision the implementation already made; earlier delivery notes that read "reuse existing Redis"
   are superseded by this point.)

## Consequences

### Positive

- **Bounded memory & cost** — TTL caps the working set; one Redis container fits the ADR-0020 envelope.
- **Fast range reads** — in-memory hash + sorted-set ops meet the NFR-07 incident-time latency budget.
- **Test isolation** — `InMemoryMetricStore` keeps the percentile/masking/extraction unit suite (NFR-05) free of any container, and `RedisStoreContractTest` proves the two backends agree.
- **Clean exit path** — the `MetricStore` seam makes InfluxDB/TimescaleDB a drop-in third impl.

### Negative / Trade-offs

- **Short retention horizon** — Redis-only limits long-horizon analysis under high path cardinality
  (source-spec §13). Accepted for initial scope; the exit path below is the recorded mitigation.
- **No durability guarantee** — a single-node Redis loss drops in-flight short-window aggregates;
  acceptable because the data is ephemeral telemetry, not a system of record (re-derivable from logs).
- **Cardinality risk** — many distinct paths × signals × buckets multiply keys; mitigated by TTL and
  monitored via a `gs_tracked_paths` gauge.

### Neutral

- TLS/encryption posture inherits ADR-0019 unchanged. Percentile method lives in the Java domain layer, not Redis.

## Exit path (recorded, not deferred silently)

When retention horizon or cardinality exceeds Redis's comfort zone, migrate `RedisMetricStore` to a
dedicated TSDB — **InfluxDB** (native retention policies + downsampling) or **TimescaleDB**
(SQL + continuous aggregates) — by adding a `MetricStore` implementation. Trigger conditions to
watch: working set > Redis memory budget, p99 query latency regression, or a requirement for
multi-day historical analysis. No API or caller change is required at that point.

## Alternatives Considered

- **PostgreSQL/TimescaleDB from day one** — rejected for initial scope: heavier operational surface
  than the ADR-0020 envelope warrants for short-horizon telemetry; kept as the exit path.
- **In-memory only (no Redis)** — rejected for prod: no cross-restart survival and no shared store if
  the service scales out; retained only as the test/local implementation.
- **Redis Streams as the store** — out of scope here; Streams' role (and its rejection _as a queue_)
  is handled in ADR-0069, not as a TS store.
- **Reuse the shared development `redis` container** — rejected (see Decision §5): it is
  host-published and persistent, which conflicts with the internal-only, ephemeral-telemetry posture
  this store needs; a dedicated profile-scoped instance keeps the workloads and durability
  guarantees separate.

## References

- `specs/system/SPEC-LGS-001-log-based-golden-signals.md` §6 (FR-06), §9.3 (retention), §13, §15-Q2
- `reports/CODE-DELIVERY-SPEC-LGS-001/specs/feature-spec.md` §1.4, §3
- ADR-0066 (Java runtime), ADR-0068 (key grammar), ADR-0019 (Redis TLS), ADR-0020 (cost)
- `docker-compose.yml` (the shared `redis` service this store is deliberately separate from — Decision §5)
