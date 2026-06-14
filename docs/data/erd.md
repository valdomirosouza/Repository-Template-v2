# Entity-Relationship Diagram

> **Owner:** Tech Lead | **Status:** Living diagram
> Logical view of the PostgreSQL tables and how they relate. **There are no database-level foreign
> keys** between these tables — the system is event-sourced and loosely coupled, so entities are
> correlated by shared identifiers (`request_id`, `agent_id`, `trace_id`), not FK constraints. The
> per-table detail (owner, PII class, encryption, retention) lives in
> `docs/data/data-model-catalog.md`; migrations in `docs/data/migrations.md`.

```mermaid
erDiagram
    REQUESTS {
        uuid id PK
        string status
        string priority
        jsonb masked_payload
        jsonb result
        text error_message
        timestamptz created_at
        timestamptz updated_at
    }
    HITL_REQUESTS_ARCHIVE {
        uuid id PK
        string agent_id
        string action_type
        jsonb action_parameters
        float risk_score
        string status
        string approver_id
        text rationale
        timestamptz created_at
        timestamptz expires_at
        timestamptz decided_at
        timestamptz archived_at
    }
    AUDIT_EVENTS {
        uuid id PK
        string event_type
        string agent_id
        string user_id
        string action
        string outcome
        float risk_score
        jsonb metadata
        string trace_id
        string approver_id
        timestamptz created_at
    }
    AGENT_MEMORY_DOCUMENTS {
        uuid id PK
        text content "AES-256-GCM"
        vector embedding
        string source
        jsonb tags
        timestamptz created_at
    }
    AGENT_CONTEXT_GRAPHS {
        uuid graph_id PK
        string session_id
        text root_goal_description
        string status
        jsonb graph_data
        timestamptz created_at
        timestamptz updated_at
    }

    REQUESTS ||..o{ AUDIT_EVENTS : "correlated by request_id (logical, no FK)"
    HITL_REQUESTS_ARCHIVE ||..o{ AUDIT_EVENTS : "correlated by agent_id / decision (logical)"
    AGENT_CONTEXT_GRAPHS ||..o{ AGENT_MEMORY_DOCUMENTS : "session context ↔ recalled memory (logical)"
```

> Dotted relationships (`..`) denote **logical correlation only** — enforced in application code and
> traces, not by the database. This is intentional (ADR-0003 async strategy, ADR-0017 memory).

## Immutability & encryption at a glance

- `audit_events`, `hitl_requests_archive` — **append-only** (UPDATE/DELETE revoked at the SQL level,
  ADR-0026/SOX).
- `agent_memory_documents.content` — **encrypted** at rest (AES-256-GCM, ADR-0018).
- All L1/L2 columns use `EncryptedField`; classification in `docs/data/data-classification.md`.

## Storage notes

- RDBMS: **Aurora PostgreSQL** (ADR-0062) with `pgvector` + `pgcrypto` (migration 0002).
- Operational state (request lifecycle, HITL pending) also lives in **Redis** — see
  `docs/data/redis-key-standards.md`.
- Event schemas (the "data in motion") are in `infrastructure/message-broker/schema-registry/avro/`.

## Related

- `docs/data/data-model-catalog.md` · `docs/data/migrations.md` · `docs/data/data-classification.md`
- `docs/reference/request-lifecycle.md` — how these tables are written during a request
