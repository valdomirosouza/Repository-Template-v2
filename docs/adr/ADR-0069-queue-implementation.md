# ADR-0069 — In-JVM Bounded Queue + Virtual-Thread Worker (Ingestion ↔ Processing Decoupling)

**Status:** Proposed
**Date:** 2026-06-11
**Authors:** Valdomiro Souza
**Reviewers:** Tech Lead
**Relates to:** [ADR-0066](ADR-0066-spec-lgs-001-runtime-stack-java-spring-boot.md) (Java 21 runtime), [ADR-0003](ADR-0003-async-api-strategy.md) (async strategy), [ADR-0020](ADR-0020-cost-governance.md) (cost)
**Scope:** `SPEC-LGS-001` only — **resolves source-spec §15-Q1** (queue implementation: in-JVM vs Redis stream vs broker).

---

## Context

FR-04 requires that validated, signal-extracted events be published to an **internal queue** that
decouples ingestion from processing, and FR-05 requires an async **worker** to drain that queue into
1m/5m aggregates. NFR-02 (as amended by ADR-0066) asks for asyncio-equivalent concurrency; ADR-0066
§Decision-2 already names **Java 21 virtual threads (Project Loom)** as that equivalent. The source
spec §15-Q1 leaves the concrete queue choice to the architecture phase, with a stated default of
"in-JVM bounded executor, honouring ADR-0003; Redis Streams stays rejected *as a queue*." ADR-0003
governs the platform async strategy and already rejects Redis Streams as a general-purpose queue.

The initial scope is **single-node** (source-spec §3, §15-Q2), so a cross-process broker is not yet
warranted, and ADR-0020 asks us to bound the queue/worker/Redis footprint.

## Decision

**Decouple ingestion from processing with an in-JVM bounded `ArrayBlockingQueue`, drained by a
single virtual-thread worker (Java 21 Loom).**

1. **Queue:** `IngestQueue` wraps `java.util.concurrent.ArrayBlockingQueue<SignalEvent>` with fixed
   capacity `INGEST_QUEUE_CAPACITY` (default `10000`, env-configurable — NFR-04, ADR-0020 bound).
   The bound is the backpressure mechanism: the queue cannot grow unboundedly under a flood.
2. **Producer (ingestion path):** uses **non-blocking** `offer()`. On success the event is queued;
   on failure (queue full) the event is counted toward the ingestion response's `rejected` count and
   `gs_queue_dropped_total` is incremented. Ingestion still returns `202` — the request layer never
   blocks on a full queue (protects the API thread, ADR-0020 / DoS resilience).
3. **Consumer (worker):** a single long-running task on
   `Executors.newVirtualThreadPerTaskExecutor()` runs a `take()` loop, applying ADR-0068 window
   bucketing/aggregation and flushing to the `MetricStore` (ADR-0067) on window roll-over and on a
   periodic timer. Virtual threads make a blocking `take()` cheap and are the Loom equivalent of the
   asyncio worker NFR-02 originally specified.
4. **ADR-0003 alignment:** **Redis Streams remains rejected *as a queue*** (consistent with ADR-0003).
   Redis is used only as the time-series **store** (ADR-0067), never as the work queue.
5. **Scale-out path (recorded):** when single-node throughput is exceeded or multi-instance/HA is
   required, replace `IngestQueue` with **Kafka** (the repo already runs Kafka via
   `services/event-worker` and `spring-kafka`). The `IngestQueue` interface is the seam; ingestion
   produces to a topic and the worker becomes a consumer. No change to extraction/aggregation logic.

## Consequences

### Positive
- **Zero new infra** for the queue — no broker to run/scan/operate in initial scope (ADR-0020).
- **Real backpressure** — the bounded queue + non-blocking `offer()` make overload an explicit,
  observable `rejected`/`dropped` signal instead of an OOM (single-node DoS resilience; threat model D).
- **Asyncio-equivalent** — Loom virtual threads satisfy NFR-02's concurrency intent (ADR-0066).
- **Clean scale-out** — the seam to Kafka is identified, not improvised later.

### Negative / Trade-offs
- **No cross-process durability** — events in the in-JVM queue are lost on process crash. Acceptable:
  the data is ephemeral telemetry, short-window, re-derivable from the HAProxy logs (same rationale as
  ADR-0067's no-durability stance). Documented, not silent.
- **Single-node only** — horizontal scale needs the Kafka exit path; not available day one (§15-Q2).
- **Drop-on-full** is a deliberate loss under flood; surfaced via metrics so it is observable, not hidden.

### Neutral
- Single worker is sufficient for initial throughput; capacity can grow to N virtual-thread workers
  draining the same queue without an architecture change if profiling shows the worker is the bottleneck.

## Alternatives Considered
- **Redis Streams as the queue** — rejected, consistent with ADR-0003 (Redis Streams rejected *as a
  queue*); keeps Redis single-purpose (store only).
- **Kafka / external broker from day one** — strongest durability and scale-out, but exceeds the
  single-node initial scope and the ADR-0020 cost envelope; retained as the explicit scale-out path.
- **Unbounded `LinkedBlockingQueue`** — rejected: removes backpressure, invites OOM under flood; the
  bound is the safety property.
- **Direct synchronous processing (no queue)** — rejected: violates FR-04's decoupling requirement and
  couples API latency to aggregation cost.

## References
- `specs/system/SPEC-LGS-001-log-based-golden-signals.md` §5 (FR-04/05), §7, §15-Q1, §15-Q2
- `reports/CODE-DELIVERY-SPEC-LGS-001/specs/feature-spec.md` §1.3, §3, §5 (E6)
- ADR-0066 (virtual threads), ADR-0003 (async strategy / Redis Streams rejection), ADR-0067 (store)
