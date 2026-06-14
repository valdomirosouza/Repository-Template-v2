# Agent Memory Governance

> **Owner:** AI Governance Lead (with DPO) | **Status:** Living policy
> Consolidates the retention, deletion, encryption, classification, and integrity controls for agent
> memory that are otherwise spread across `specs/ai/agent-memory.md`, ADR-0017, `src/shared/config.py`,
> and the migrations. The architecture spec remains authoritative on _how_ memory works; this page is
> the _governance_ view — what is allowed, retained, deleted, and audited.

Memory has three layers (`specs/ai/agent-memory.md`):

| Layer           | Backend               | Scope                      | TTL / retention                    |
| --------------- | --------------------- | -------------------------- | ---------------------------------- |
| Semantic memory | PostgreSQL + pgvector | specs, ADRs, past outcomes | 90 days (aligns ADR-0013)          |
| Session cache   | Redis                 | active sprint context      | `memory_session_ttl_seconds` (24h) |
| Bug history     | pgvector + audit      | HITL rejection patterns    | 90 days                            |

---

## Classification & PII

- **Every write to any layer MUST pass `pii_filter` (`mask_text`/`mask_dict`) before persisting**
  (`specs/ai/agent-memory.md`; CLAUDE.md §3.1). Embeddings are computed from masked text only.
- Permitted identifiers: agent UUIDs (L3); user identity only as `[USER_ID]` tokens — never raw.
- Any new memory write category requires DPIA/RIPD review (ADR-0017).
- Classification levels: `docs/data/data-classification.md` (authoritative scheme in `specs/privacy/pii-inventory.md`).

## Encryption

- Semantic-memory `content` is **AES-256-GCM** encrypted at rest (`enc:v1:...`, migration
  `0003_create_agent_memory_documents.py`, `src/shared/db_encryption.py`, ADR-0018).
- Redis session memory uses `rediss://` + TLS in production (ADR-0019).
- Key sourced from `DB_ENCRYPTION_KEY` (Vault in prod); rotation per ADR-0018.

## Retention & deletion

| Data                | Retention                 | Deletion mechanism                                          |
| ------------------- | ------------------------- | ----------------------------------------------------------- |
| Semantic / bug docs | 90 days from `created_at` | scheduled hard delete (`specs/privacy/data-retention.md`)   |
| Session cache       | 24h (TTL)                 | Redis TTL eviction                                          |
| DSAR erasure        | within 15 days            | delete all docs where `agent_id`/subject matches (ADR-0017) |

DSAR / right-to-erasure requests are handled per `data-subject-rights` workflow; memory is in scope.
Emit deletion metrics (`data_retention_deleted_total{category}`) and alert on overdue L1/L2.

## Integrity — memory poisoning (target controls, not yet implemented)

Retrieval-augmented memory can be poisoned (a malicious or low-quality entry steers future
reasoning). The following are **recommended target controls**, not current behaviour — do not cite as
implemented:

- **Provenance:** record source + writer (`agent_id`, session) on every memory doc; prefer trusted
  sources (`specs/`, `docs/adr/`) over free-text agent output.
- **Write gating:** bug-history/semantic writes from agent output pass the output sanitizer
  (`src/guardrails/output_sanitizer.py`) before indexing.
- **Anomaly detection:** flag unusual write spikes or low-similarity outliers for review
  (`agent_behavioral_anomaly_total` — `docs/ai/ai-observability-naming.md`).
- **Versioning & rollback:** keep memory writes append-friendly so a poisoned batch can be excised.

## Access & audit

- Memory reads/writes occur inside instrumented agent spans (`agent.*` — see observability naming).
- Vector store is access-controlled at the DB role; audit-relevant writes flow through the immutable
  audit log (`audit_events`, ADR-0026).

## Memory governance checklist (new memory category)

- [ ] PII masking applied before write; embeddings from masked text
- [ ] Classification assigned; DPIA flagged if new PII processing
- [ ] Retention + deletion path defined (TTL or scheduled delete); DSAR erasure covered
- [ ] Encryption confirmed for at-rest content (L1/L2)
- [ ] Provenance recorded; write gated by output sanitizer where agent-generated

---

## Related

- `specs/ai/agent-memory.md` (authoritative architecture) · ADR-0017
- `specs/privacy/data-retention.md` · `docs/data/data-classification.md`
- `src/shared/db_encryption.py` (ADR-0018) · ADR-0019
- `docs/ai/ai-observability-naming.md` · `skills/ai/guardrails.md`
