# RB-SRE-GS-001 — golden-signals store unavailable

**Trigger:** `/analytics/health` returns 503 (`store_connected=false`), or `StoreUnavailableException` rate rises. With the Redis store (ADR-0067), Redis is down/unreachable; with the in-memory store, the process restarted (data is volatile).

**Impact:** `/analytics` and `/analytics/paths` degrade; the agent/SRE loses the Golden-Signal read path. Ingestion may still 202 but aggregates aren't queryable.

**Diagnose:**

1. `curl -s localhost:${APP_PORT:-8085}/analytics/health` → check `store_connected`, `tracked_paths`.
2. `curl -s localhost:${APP_PORT:-8085}/actuator/health` → liveness/readiness.
3. Scrape `/actuator/prometheus` for queue depth + `gs_aggregate_freshness_seconds`.

**Mitigate:**

- Redis store: restore/failover Redis; the service has **no in-app fallback** (ADR-0067) — recovery = restore the store or roll back (see Phase-13 deploy-rollback).
- In-memory store: restart is the recovery; recent aggregates are lost by design (retention 1m:2h / 5m:24h).
- If the bounded queue is saturated (drop counter rising), reduce ingest rate (per-key 429 already caps it) or scale.

**Escalate:** if store-restore exceeds RTO `dora_mttr_target_seconds: 3600`, page SRE Lead.
