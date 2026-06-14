# Database Migrations Guide

> **Owner:** Tech Lead | **Status:** Living guide
> How schema changes are made, applied, and rolled back. Migrations are Alembic revisions in
> `alembic/versions/` (config: `alembic.ini`, env: `alembic/env.py`). The resulting tables are
> cataloged in `docs/data/data-model-catalog.md` and diagrammed in `docs/data/erd.md`.

---

## Current migrations

| Rev  | File                                    | Creates / does                                                                |
| ---- | --------------------------------------- | ----------------------------------------------------------------------------- |
| 0001 | `0001_create_audit_events.py`           | `audit_events` (+ indexes) and **REVOKE UPDATE/DELETE** (immutable, ADR-0026) |
| 0002 | `0002_enable_pgcrypto_vector.py`        | enable `pgcrypto` + `vector` (pgvector) extensions                            |
| 0003 | `0003_create_agent_memory_documents.py` | `agent_memory_documents` (encrypted `content`, IVFFlat index)                 |
| 0004 | `0004_create_requests.py`               | `requests` (domain request lifecycle)                                         |
| 0005 | `0005_create_hitl_archive.py`           | `hitl_requests_archive` (append-only HITL history)                            |
| 0006 | `0006_add_context_graph_table.py`       | `agent_context_graphs` (session context, JSONB)                               |

## Common commands

```bash
uv run alembic upgrade head                      # apply all pending migrations
uv run alembic current                           # show the applied revision
uv run alembic history                           # list revisions
uv run alembic revision --autogenerate -m "msg"  # generate a migration from model changes
uv run alembic downgrade -1                       # roll back one revision (rehearse in staging first)
```

## Authoring a migration

1. Make the model/schema change, then `--autogenerate` the revision and **review it by hand** —
   autogenerate misses some changes (CHECK constraints, server defaults, data backfills).
2. **Classify every new column** (L1–L4) and apply `EncryptedField` to L1/L2 at-rest columns
   (ADR-0018). Update `docs/data/data-classification.md` + `data-model-catalog.md` + the ERD.
3. **Immutability:** audit/append-only tables must `REVOKE UPDATE, DELETE` from the app role in the
   migration (pattern: `0001_create_audit_events.py`); never rely on app code alone (ADR-0026/SOX).
4. **Indexes:** name them `ix_<table>_<columns>`; add indexes for the access patterns the catalog lists.
5. Provide a real `downgrade()` and **rehearse it in staging** — a migration you can't reverse is a
   production risk (RB-001 rollback).
6. New PII processing ⇒ flag DPIA/RIPD (CLAUDE.md §3.1).

## Applying & rolling back

- **Deploy:** `alembic upgrade head` runs as part of the release (see `Makefile`, `make setup`).
- **Rollback:** schema rollback is `alembic downgrade <rev>`, staged first — see
  `docs/runbooks/rollback-procedure.md` (RB-001) and `docs/resilience/backup-restore-policy.md` for
  the data-restore path (Aurora PITR).
- **Forward-fix preferred:** for already-released migrations, prefer a new corrective migration over a
  downgrade in production.

## Testing

- Migration round-trip (`upgrade` then `downgrade`) should be covered in integration tests.
- Retention/TTL behaviour and immutability (UPDATE/DELETE rejected on audit tables) are good
  candidates for explicit tests — see `skills/engineering/testing-strategy.md`.

## Related

- `docs/data/data-model-catalog.md` · `docs/data/erd.md` · `docs/data/data-classification.md`
- ADR-0018 (encryption) · ADR-0026 (audit immutability) · ADR-0062 (Aurora)
- `docs/runbooks/rollback-procedure.md` · `docs/resilience/backup-restore-policy.md`
