# ADR-0017 — Agent Memory Architecture

**Status:** Accepted
**Date:** 2026-05-27
**Authors:** Tech Lead, DPO
**Supersedes:** —
**Superseded by:** —

---

## Context

Agents operating across multiple sessions have no recall of prior decisions,
past HITL rejections, or relevant architectural constraints in specs and ADRs.
This causes repeated errors and forces human reviewers to re-explain context
that was already covered in previous sessions.

Requirements:

- **Long-term recall:** agents must be able to retrieve semantically relevant
  spec/ADR content and past rejection patterns without loading every document
- **Short-term context:** harness coordinator needs to persist sprint context
  across context resets (supplements the existing ContextSnapshot mechanism)
- **Privacy-safe:** no raw PII may be stored; pii_filter is mandatory at every
  write boundary; DPIA required before merge
- **Testable without external services:** InMemory implementations for both
  vector store and session cache

---

## Decision

Use a **three-layer memory architecture**:

| Layer           | Technology            | Rationale                                             |
| --------------- | --------------------- | ----------------------------------------------------- |
| Semantic memory | PostgreSQL + pgvector | Co-located with existing DB; no new infra; ACID       |
| Session cache   | Redis                 | Already deployed (caching ADR-0009); TTL native       |
| Bug history     | pgvector (same DB)    | Reuses vector store; semantic retrieval of rejections |

**Why pgvector over a dedicated vector DB:**

- Pinecone, Weaviate, Qdrant — all add a new external service to operate
- pgvector runs as a Postgres extension — zero new infra, uses the existing
  DB pool, same backup/restore, same access control
- At the scale of spec/ADR documents (hundreds, not millions), pgvector's
  HNSW index provides sub-10 ms retrieval

**Why not store embeddings in Redis:**

- Redis RediSearch has vector support but requires an additional module;
  our Redis deployment (ADR-0009) does not guarantee this module is loaded
- Session cache is ephemeral; long-term memory must survive Redis restarts

**Embedder neutrality:**

- The `Embedder` protocol accepts any float-vector provider
- Production embedder is injected at the application boundary
- No hard dependency on a specific embedding model

---

## Consequences

### Positive

- Zero new infrastructure — pgvector + Redis already deployed
- `InMemoryVectorStore` and `fakeredis` enable full unit testing without services
- PII-safe by construction: pii_filter enforced at module boundary
- Semantic retrieval enables agents to find relevant past context without
  brittle keyword matching

### Negative

- pgvector requires the `vector` extension to be enabled in the Postgres instance
  (Alembic migration needed before production deploy)
- Embedding dimension is fixed per deployment — changing models requires
  re-indexing all existing documents
- Adds `memory_*` Prometheus metrics (minor observability surface increase)

### Neutral

- DPIA sign-off required before merge (`docs/privacy/dpia/dpia-agent-memory.md`)
- Deletion on erasure request: documents indexed by `agent_id` must be purged
  within 15 days

---

## Alternatives Considered

| Alternative          | Reason rejected                                                     |
| -------------------- | ------------------------------------------------------------------- |
| Pinecone SaaS        | External dependency; SaaS lock-in; PII concerns with third party    |
| Weaviate self-hosted | New service to operate; heavier than pgvector for current scale     |
| Redis RediSearch     | Module availability uncertain; session cache is not durable storage |
| File-based cache     | Not queryable; no semantic search; no TTL management                |

---

## Implementation Reference

- `specs/ai/agent-memory.md` — full acceptance criteria and component contracts
- `src/memory/vector_store.py` — VectorStore protocol + InMemory + Postgres implementations
- `src/memory/document_indexer.py` — DocumentIndexer (specs/ + docs/adr/)
- `src/memory/session_memory.py` — SessionMemory (Redis-backed)
- `src/memory/bug_history_store.py` — BugHistoryStore (pgvector + audit)
- `docs/privacy/dpia/dpia-agent-memory.md` — DPIA (DPO sign-off required)
- `tests/unit/memory/` — unit tests with InMemory and fakeredis implementations
