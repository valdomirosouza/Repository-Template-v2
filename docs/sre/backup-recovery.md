# Backup & Recovery (consolidated)

> **Owner:** SRE Lead (with DPO for data-loss/compliance) | **Status:** Living doc
> The **single per-store view** of recovery objectives, backup mechanism, and restore pointers for
> the stateful stores. This doc **consolidates and cross-links**; it does not restate the documents
> it points to:
>
> - `docs/resilience/dr-plan.md` (RB-002) — DR **governance view**; authoritative for per-component
>   RTO/RPO during an actual event.
> - `docs/resilience/backup-restore-policy.md` — authoritative for **backup mechanism, retention,
>   and the restore operator procedures**.
> - `docs/ai/memory-governance.md` + ADR-0017 — governance for the agent-memory stores.
>
> Where a number here overlaps `dr-plan.md`/RB-002, **those remain authoritative** and this table
> mirrors them with a back-link. Established by **ADR-0082**.

---

## Per-store recovery table

| Store                                 | RPO (max data loss)        | RTO (max downtime)      | Backup mechanism                                                                 | Backup cadence                       | Restore procedure pointer                                                               |
| ------------------------------------- | -------------------------- | ----------------------- | -------------------------------------------------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------- |
| **PostgreSQL (Aurora)**               | 1h (last backup) / PITR    | 30 min                  | Aurora automated backups + PITR; monthly manual KMS snapshot                     | PITR continuous; snapshot monthly    | `backup-restore-policy.md` → "Database — point-in-time restore"; RB-002 (ADR-0062)      |
| **Redis — session cache**             | 15 min                     | 15 min                  | ElastiCache daily snapshot; session state is reconstructible                     | daily snapshot                       | `backup-restore-policy.md` → "Kafka / Redis"; agent-session recovery RB-SRE-005         |
| **Redis — time-series (ADR-0067)**    | 15 min (snapshot)          | 15 min                  | ElastiCache daily snapshot; no in-app fallback (ADR-0067)                        | daily snapshot                       | `backup-restore-policy.md` → "Kafka / Redis"; store-unavailable RB-SRE-GS-001           |
| **pgvector (semantic + bug history)** | follows Aurora (1h / PITR) | follows Aurora (30 min) | Extension co-located in the Aurora cluster (ADR-0017) — restored with PostgreSQL | with PostgreSQL (no separate backup) | restored as part of the Aurora restore above; governance `docs/ai/memory-governance.md` |

Notes:

- **pgvector has no independent objective.** Semantic memory and bug-history vectors live in the
  Aurora Postgres cluster as the `vector` extension (ADR-0017); they are backed up and restored
  **with** PostgreSQL, so their RPO/RTO are exactly Aurora's. We record this explicitly rather than
  inventing separate numbers (ADR-0082 §Consequences/Neutral).
- **Audit log** (RPO 0 / RTO 15 min, append-only, replicated — ADR-0026, ADR-0075) and **Kafka**
  (RPO 0 via replay) are recovery components covered in `dr-plan.md`; they are not snapshot-restore
  stores in the sense of this table and are listed there, not duplicated here.
- All backups are **encrypted** (customer-managed KMS for Aurora; AES-256-GCM at the app layer for
  L1/L2 content — ADR-0018/ADR-0019). Restored data retains its original PII classification and
  retention caps (`docs/data/data-classification.md`).

For the full per-component DR table (api-gateway, agent-service, event-consumer, audit) see
`docs/resilience/dr-plan.md` § Recovery objectives.

---

## Restore-drill verification

> A backup that has never been restored is not a proven backup. The drill closes that loop on a
> schedule and produces dated evidence (ADR-0082).

- **Cadence:** monthly (aligned with the verification cadence already stated in
  `backup-restore-policy.md` and `dr-plan.md`).
- **What it verifies:**
  1. The **latest** backup/snapshot can be restored into a **scratch, throwaway** store (never the
     live or prod store).
  2. **Integrity** of the restored data — row counts within expected bounds, a **known canary key**
     is present, and (for Postgres) `alembic current` matches the expected migration head.
  3. The **RTO achieved** is recorded and compared against the per-store RTO above.
- **Evidence:** each drill is recorded as `docs/resilience/restore-drills/YYYY-MM-DD.md` (format and
  template: `docs/resilience/restore-drills/README.md`). Evidence records **counts/hashes, never raw
  rows** — no PII leaves the scratch environment.
- **Pass/fail criteria:**
  - **Pass:** restore completed, integrity checks all green, RTO ≤ the store's documented RTO.
  - **Fail:** restore failed, any integrity check red, or RTO exceeded — pages SRE and opens a
    GitHub Issue labelled `incident`; the drill is re-run after remediation.
- **How to run it:** runbook `docs/sre/runbooks/RB-SRE-006-restore-drill.md`, driven by the
  automation scaffold `scripts/backup/restore_drill.sh` (a `--dry-run`-by-default, non-destructive
  stub until wired to real backups — ADR-0082).
- **Schedule (wired):** the drill runs on a cadence via `.github/workflows/restore-drill.yml`
  (weekly, Monday 06:23 UTC; also `workflow_dispatch` + on PRs touching the script) across all
  three stores in `--dry-run` mode — keeping the drill runnable and the cadence visible. It flips
  to real drills once `--execute` is implemented and the script's safety guard is removed.

### Backup freshness alert — `backup_last_success_timestamp`

Independently of the drill, a freshness signal catches a **missing or stale** backup before the
next drill would:

- Each successful backup job emits `backup_last_success_timestamp{store="<name>"}` (Unix seconds).
- Alert when `time() - backup_last_success_timestamp{store=...}` exceeds the store's backup cadence
  plus a grace window (e.g. > 26h for a daily snapshot) → **page SRE**.
- This closes the second gap recorded in `backup-restore-policy.md` ("no automated backup-success
  metric/alert wired yet"). The metric/alert wiring remains target-state until the backup jobs emit
  it; this doc defines the contract.

The drill and the freshness alert are **independent** signals: the alert proves a backup _exists and
is recent_; the drill proves that backup _actually restores_.

---

## Related

- `docs/resilience/dr-plan.md` (RB-002) — DR governance view, authoritative per-component RTO/RPO
- `docs/resilience/backup-restore-policy.md` — backup mechanism/retention + restore operator procedures
- `docs/resilience/restore-drills/README.md` — drill evidence convention
- `docs/sre/runbooks/RB-SRE-006-restore-drill.md` — drill procedure
- `scripts/backup/restore_drill.sh` — restore-drill automation scaffold (dry-run stub)
- ADR-0082 (this consolidation) · ADR-0062 (Aurora) · ADR-0067 (Redis time-series) · ADR-0017 (agent memory) · ADR-0026 (audit immutability) · ADR-0075 (fallback policy)
- `docs/sre/slo/slo.yaml` — RTO/MTTR target (`dora_mttr_target_seconds: 3600`)
