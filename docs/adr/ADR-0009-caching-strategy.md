# ADR-0009 — Caching Strategy

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead, SRE Lead

---

## Context

The system has two distinct caching needs:

1. **Hot cache (L2):** Session state, rate limit counters, HITL request state,
   and frequently-read configuration. Requires sub-millisecond read latency and
   TTL-based eviction. Data is structured key-value.

2. **Semantic cache (L3):** RAG (Retrieval-Augmented Generation) — embedding-based
   similarity search over pseudonymised historical decisions, runbook summaries,
   and knowledge base entries. Requires approximate nearest-neighbour (ANN) search
   with cosine similarity. Data is high-dimensional float vectors.

A single caching tier cannot serve both workloads efficiently.

---

## Decision

Adopt a **two-tier caching architecture**:

| Tier | Technology                     | Use cases                                                       | Eviction          | PII handling                   |
| ---- | ------------------------------ | --------------------------------------------------------------- | ----------------- | ------------------------------ |
| L2   | Redis 7                        | Session state, rate limiting, HITL request store, feature flags | TTL + LRU         | Masked before write (ADR-0012) |
| L3   | Vector DB (pgvector or Qdrant) | RAG semantic cache, knowledge base retrieval                    | ANN index pruning | Pseudonymised before indexing  |

### Redis configuration

- `maxmemory-policy: allkeys-lru` — prevent OOM by evicting least-recently-used keys
- `maxmemory: 512mb` (staging), `2gb` (production)
- Sentinel or Cluster mode for HA in production
- All writes go through `src/shared/` service layer — no direct Redis access from API

### Vector DB configuration

- Documents pseudonymised (PII masked, entity IDs replaced with stable hashes) before indexing
- Embeddings generated server-side — raw text never sent to external embedding API without masking
- Index backed up daily to object storage

---

## Consequences

### Positive

- Redis provides O(1) key-value operations at sub-millisecond latency — suitable for
  rate limiting (HITL queue depth, agent action counters) and session lookups.
- Setting `maxmemory-policy: allkeys-lru` prevents the Redis OOM condition documented
  in postmortem INC-001.
- Vector DB enables the agent to retrieve contextually similar past decisions,
  reducing LLM token consumption and improving response consistency.
- Two-tier isolation ensures that Vector DB ANN index size growth does not affect
  Redis key-value latency.

### Negative / Trade-offs

- Two caching systems to operate, monitor, and back up.
- pgvector (Postgres extension) is simpler operationally but slower for large indices;
  Qdrant is faster but adds a separate service. Choice deferred to implementation.
- Cache invalidation for the L3 vector cache is non-trivial when pseudonymised
  documents are updated.

---

## Alternatives Considered

**Redis alone (no vector DB)**
Rejected: Redis does not support ANN search natively at the scale required for RAG.
RedisSearch with VSS is viable but couples vector search to the same cluster as
hot-path rate limiting — a Vector DB query spike could starve the rate limiter.

**Memcached**
Rejected: no native TTL expiry per key type; no persistence; no Lua scripting for
atomic rate-limit increment operations; inferior ecosystem vs. Redis.

**In-process cache (functools.lru_cache)**
Rejected: not shared across pod replicas; no TTL; cache warm-up on every pod restart
degrades performance during canary rollout.
