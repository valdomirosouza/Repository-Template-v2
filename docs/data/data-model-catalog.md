# Data Model Catalog

> **Owner:** Tech Lead (with DPO for classification) | **Status:** Living reference
> Inventory of every persistent entity and event schema, with its owner, storage, PII
> classification, encryption, and retention. Classification levels are defined authoritatively in
> `specs/privacy/pii-inventory.md`; retention in `specs/privacy/data-retention.md`. Verify against
> the migrations/schemas before relying on a row — code wins over this doc.

Legend: **Class.** = highest PII level present (L1–L4, see `docs/data/data-classification.md`).
**Enc.** = field-level AES-256-GCM (`src/shared/db_encryption.py`, ADR-0018/0019).

---

## 1. PostgreSQL tables (Aurora — ADR-0062; migrations in `alembic/versions/`)

| Table                    | Migration | Owner         | Purpose                                | Class. | Enc.                     | Retention             | Notes                                              |
| ------------------------ | --------- | ------------- | -------------------------------------- | ------ | ------------------------ | --------------------- | -------------------------------------------------- |
| `audit_events`           | 0001      | platform-team | Immutable agent/action audit trail     | L3     | —                        | 5y (archive after 1y) | INSERT-only (UPDATE/DELETE revoked); ADR-0011/0026 |
| `agent_memory_documents` | 0003      | platform-team | Vector memory (pgvector) + source docs | L2     | ✓ `content`              | 1y                    | IVFFlat index; ADR-0017/0018                       |
| `requests`               | 0004      | platform-team | Domain request lifecycle               | L2     | — (payload **masked**)   | L2 1y / L1 90d        | `masked_payload`, `status`, `result`; ADR-0003     |
| `hitl_requests_archive`  | 0005      | platform-team | Durable HITL decision history          | L2     | — (params masked/hashed) | 5y                    | append-only; `approver_id`, `rationale`; ADR-0011  |
| `agent_context_graphs`   | 0006      | platform-team | Session context graph (autonomy tier)  | L3     | —                        | session + policy      | `graph_data` JSONB; ADR-0041                       |
| _pgvector + pgcrypto_    | 0002      | platform-team | DB extensions enablement               | —      | —                        | —                     | enables vector index + crypto functions            |

Index convention: `ix_<table>_<columns>` (e.g. `ix_audit_events_agent_created` on `(agent_id, created_at)`).
Immutability is enforced at the DB role (UPDATE/DELETE revoked on `audit_events`, `hitl_requests_archive`).

## 2. Pydantic domain models (`src/shared/models.py`)

| Model                | Role                                                       | Notes                                          |
| -------------------- | ---------------------------------------------------------- | ---------------------------------------------- |
| `BaseModel`          | common `id` (UUID), `created_at`, `updated_at`             | base for the below                             |
| `AgentActionRequest` | proposed agent action (risk_score, requires_hitl, context) | feeds the HITL gateway                         |
| `AgentActionResult`  | outcome after safety gates                                 | `status`, `output`/`error`/`hitl_decision`     |
| `AuditEvent`         | immutable audit record                                     | maps to `audit_events`; written before execute |

## 3. Redis keys (operational store — `rediss://` + TLS in prod, ADR-0019)

| Key pattern                  | Holds                            | TTL / config (`src/shared/config.py`)   | Encrypted    |
| ---------------------------- | -------------------------------- | --------------------------------------- | ------------ |
| `hitl:req:{request_id}`      | active HITL request (JSON)       | grace `hitl_redis_ttl_grace_hours` (4h) | ✓ if key set |
| `hitl:pending`               | sorted set, score = `expires_at` | —                                       | n/a          |
| `hitl:expired:{request_id}`  | archived HITL request            | `hitl_expired_ttl_days` (7d)            | ✓ if key set |
| `request:state:{request_id}` | request lifecycle state          | `request_result_ttl_hours` (24h)        | —            |

Prefixes are configurable (`hitl_redis_key_prefix`, `request_redis_key_prefix`). Key sources:
`src/agents/hitl_store.py`, `src/agents/request_store.py`.

## 4. Avro event schemas (`infrastructure/message-broker/schema-registry/avro/`)

All envelopes share `event_id`, `schema_version`, `produced_at`, `trace_id`, `producer_service`, and
a nested `payload`. **PII is masked before publish** (ADR-0012); params are stored as SHA-256 hashes,
never raw. Topic ↔ schema mapping is governed by `services.yaml` and validated by
`scripts/governance/check_traceability.py` (Wave 1).

| Schema (`*-v1.avsc`)                  | Topic (`services.yaml`)    | Key payload fields                                                            |
| ------------------------------------- | -------------------------- | ----------------------------------------------------------------------------- |
| `request-created`                     | `request.created.v1`       | `request_id`, `agent_id?`, `action`, `risk_score?`, `oversight_mode`          |
| `hitl-decision`                       | `hitl.decision.v1`         | decision, `approver_id`, rationale                                            |
| `audit-event`                         | `audit.event.v1`           | `audit_event_id`, `action`, `outcome`, `risk_score?`, `guardrails_passed[]`   |
| `domain-entity-created`               | `domain.entity.created.v1` | entity id/type, change set                                                    |
| `domain-entity-updated`               | `domain.entity.updated.v1` | entity id/type, change set                                                    |
| `event-processed`                     | `event.processed.v1`       | completion envelope                                                           |
| `domain-request-dlq`                  | `domain.request.dlq`       | failed message + failure metadata (30d window, REM-012)                       |
| `agent_action` _(unversioned legacy)_ | —                          | `action_type`, `action_params_hash`, `risk_score`, `context_summary` (masked) |

Legacy unversioned schemas (`domain_request.avsc`, `domain_result.avsc`, `hitl_decision.avsc`,
`audit_event.avsc`) predate the `-v1` envelope convention; prefer the versioned files for new work.

---

## How to add an entity

1. Write the migration (`uv run alembic revision --autogenerate -m "..."`) and/or the Avro schema.
2. Classify every new field (L1–L4) and apply `EncryptedField` to L1/L2 columns (ADR-0018).
3. Add the row to this catalog **and** to `specs/privacy/pii-inventory.md` if it introduces PII.
4. If it adds a topic, register it in `services.yaml` (+ `docs/api/asyncapi/v1/asyncapi.yaml`).
5. Flag DPIA/RIPD review for any new PII processing (CLAUDE.md §3.1).

---

## Related

- `docs/data/data-classification.md` · `specs/privacy/pii-inventory.md`
- `specs/privacy/data-retention.md` · ADR-0013 (retention)
- `src/shared/db_encryption.py` (ADR-0018) · ADR-0019 (Redis TLS)
- `services.yaml` · `scripts/governance/check_traceability.py`
