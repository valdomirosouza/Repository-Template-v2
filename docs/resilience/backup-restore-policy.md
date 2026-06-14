# Backup & Restore Policy

> **Owner:** SRE Lead (with DPO) | **Status:** Living policy
> Consolidates the backup retention that today lives in `specs/privacy/data-retention.md` and
> `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md`, and documents the restore +
> verification procedure. Backups are **managed by the cloud platform (Aurora/MSK/ElastiCache)**;
> the restore steps below are operator procedures, not yet automated scripts (see Gaps).

---

## Backup policy by store

| Store                  | Mechanism                                         | Retention                                       | Source                            |
| ---------------------- | ------------------------------------------------- | ----------------------------------------------- | --------------------------------- |
| PostgreSQL (Aurora)    | automated backups + PITR; monthly manual snapshot | PITR 7d (prod) / 1d (non-prod); snapshot **1y** | SPEC-INFRA-001; ADR-0062          |
| Kafka (MSK)            | daily snapshot                                    | 7 days                                          | SPEC-INFRA-001                    |
| Redis (ElastiCache)    | daily snapshot                                    | 7 days                                          | SPEC-INFRA-001                    |
| Object storage backups | lifecycle-managed                                 | 30 days (RPO window)                            | `specs/privacy/data-retention.md` |
| CloudWatch logs        | retention policy                                  | 90d (prod) / 30d (non-prod)                     | SPEC-INFRA-001                    |

All backups are **encrypted** (customer-managed KMS for Aurora; AES-256-GCM at the app layer for
L1/L2 content — ADR-0018/0019). PII retention caps still apply to restored data (`docs/data/data-classification.md`).

## Restore procedures (operator templates)

> These are **reference procedures**, not turnkey scripts — fill in environment-specific identifiers
> and **always rehearse in staging first** (RB-001/RB-002). Do not run against prod without an
> approved change (ISO 27001 / `skills/change-management/deploy-rollback.md`).

**Database — point-in-time restore (Aurora):**

1. Identify the target timestamp (just before corruption/loss).
2. Restore the cluster to a new identifier via PITR (console/IaC); do **not** overwrite the live cluster.
3. Validate integrity (row counts, latest audit event, `alembic current` matches expected head).
4. Cut over (DNS/endpoint) during a maintenance window; keep the old cluster until validated.

**Migration rollback (schema-level):** `uv run alembic downgrade <rev>` — staged first (RB-001).

**Kafka / Redis:** restore from the managed daily snapshot to a new node; replay DLQ
(`docs/sre/runbooks/dlq-accumulating.md`) after broker recovery — events are not lost (RPO 0 via replay).

## Backup verification & drills

- **Monthly:** restore the latest DB snapshot into a throwaway test environment and run integrity
  checks (RB-002). A backup that has never been restored is not a backup.
- **Evidence convention:** record each drill under `docs/resilience/restore-drills/YYYY-MM-DD.md`
  with: what was restored, RTO achieved, integrity result, issues, owner. (Create the folder on first drill.)
- **Alert:** missing/failed scheduled backups should page SRE (wire to the backup job's status metric).

## Gaps & target state (not yet implemented — do not cite as done)

- **No scripted restore** (`scripts/backup/`/`scripts/restore/`) yet — procedures are manual. Target:
  parameterised, staging-tested restore scripts invoked from the runbooks.
- **No automated backup-success metric/alert** wired yet — target: emit `backup_last_success_timestamp`
  and alert on staleness.

---

## Related

- `docs/runbooks/disaster-recovery.md` (RB-002) · `docs/runbooks/rollback-procedure.md` (RB-001)
- `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md` · ADR-0062 (Aurora)
- `specs/privacy/data-retention.md` · `docs/data/data-classification.md`
- `docs/resilience/dr-plan.md`
