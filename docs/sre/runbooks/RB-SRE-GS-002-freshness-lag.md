# RB-SRE-GS-002 — aggregate freshness lag (worker backlog)

**Trigger:** `gs_aggregate_freshness_seconds` breaches the SLO (90 s [CONFIRM]); `/analytics` returns stale buckets; ingest-queue depth climbing toward `INGEST_QUEUE_CAPACITY` (10000), drop counter rising.

**Impact:** Golden Signals lag reality (G-01 violated) → the agent/SRE reasons on stale data; MTTD benefit erodes.

**Diagnose:**

1. `/actuator/prometheus` → queue depth, drop counter, `gs_aggregate_freshness_seconds`, worker throughput.
2. Confirm the virtual-thread `AggregationWorker` is draining (not deadlocked) — check logs for the drain loop + `trace_id`.

**Mitigate:**

- Transient burst: per-key rate limit (429) + bounded queue shed load by design; wait for drain.
- Sustained: scale the service horizontally (stateless API + worker) or raise `INGEST_QUEUE_CAPACITY` with headroom; if the store write is the bottleneck (Redis), check store latency (→ RB-SRE-GS-001).
- Window-boundary bursts can transiently inflate lag (ADR-0068 left-closed/right-open semantics) — expected, self-corrects.

**Escalate:** persistent breach > 15 min or drop counter non-zero and rising → SRE Lead.
