# RB-SRE-006 — Backup Restore Drill

**Owner:** SRE Lead (with DPO for data-loss/compliance) | **Last updated:** 2026-06-15
**Spec:** N/A — operational policy
**ADR:** ADR-0082
**Related:** RB-002 (Disaster Recovery), RB-001 (Rollback), RB-SRE-005 (Agent Session Recovery)

---

## When to Use This Runbook

Run on the **monthly schedule** (and after any change to a backup mechanism) to **prove** that the
latest backup of a stateful store actually restores. A backup that has never been restored is not a
proven backup (ADR-0082). Use it to:

- Restore the latest backup into a **scratch, throwaway** store.
- Verify integrity (row counts, a known canary key, `alembic current`).
- Record dated evidence under `docs/resilience/restore-drills/`.

Per-store objectives and the backup mechanism are in `docs/sre/backup-recovery.md`. This runbook is
the **procedure**; the policy lives in that doc and `docs/resilience/backup-restore-policy.md`.

> **Safety rails.** Never restore over a live or prod store. Always restore to a **new** identifier.
> Running against prod requires an approved change (ISO 27001 /
> `skills/change-management/deploy-rollback.md`). Evidence files record **counts/hashes, never raw
> rows** — no PII leaves the scratch environment.

---

## 1. Pick the Store and the Backup

1. Choose the store for this drill (rotate across PostgreSQL/Aurora, Redis session, Redis
   time-series). See the per-store table in `docs/sre/backup-recovery.md`.
2. Identify the **latest** backup/snapshot and note its timestamp (its age at restore time).

---

## 2. Dry-Run the Drill Scaffold First

The automation scaffold is **inert by default** (`--dry-run`). Run it to print the planned steps
before touching any infrastructure:

```bash
# Default is --dry-run; prints the plan, makes no infra calls.
scripts/backup/restore_drill.sh --store postgres
```

Confirm the printed plan matches the store and backup you intend to restore. Until the scaffold is
wired to real backups, perform the restore manually (steps 3–5) and use the scaffold only to record
the evidence skeleton.

---

## 3. Restore into a Scratch Store

Follow the per-store restore pointer from `docs/sre/backup-recovery.md` /
`docs/resilience/backup-restore-policy.md`:

- **PostgreSQL (Aurora):** restore the latest snapshot or PITR target to a **new** cluster
  identifier (console/IaC). Do **not** overwrite the live cluster. (ADR-0062)
- **Redis (session / time-series):** restore the latest daily snapshot to a **new** node. (ADR-0067
  for time-series; the store has no in-app fallback.)

Start a wall-clock timer when the restore begins to measure RTO.

---

## 4. Verify Integrity

- **Row counts** within expected bounds (compare to the source store's approximate counts).
- **Canary key present** — confirm a known sentinel key/record restored intact.
- **PostgreSQL only:** `uv run alembic current` matches the expected migration head.

```bash
# Postgres example (against the SCRATCH endpoint, not prod):
PGURL="postgresql://...scratch-endpoint..." uv run alembic current
# Redis example (against the SCRATCH node):
redis-cli -u "rediss://...scratch-node..." EXISTS "<canary-key>"
```

If any check fails → the drill **FAILS** (step 6).

---

## 5. Record Evidence

Create `docs/resilience/restore-drills/YYYY-MM-DD.md` using the template in
`docs/resilience/restore-drills/README.md`. Record store, backup id + age, scratch target, integrity
results, **RTO achieved vs documented RTO**, PASS/FAIL, issues, and owner. Counts/hashes only — no
raw rows.

---

## 6. Pass / Fail and Tear-Down

- **PASS:** restore completed, all integrity checks green, RTO ≤ the documented RTO. Commit the
  evidence file. **Destroy the scratch store.**
- **FAIL:** restore failed, any integrity check red, or RTO exceeded.
  1. Open a GitHub Issue labelled `incident` with the evidence file linked.
  2. Page the SRE Lead (and DPO if data loss is implicated).
  3. Remediate, then re-run the drill and add a new dated evidence record.
  4. Still destroy the scratch store.

---

## 7. Escalation

- Restore cannot complete within the documented RTO, or the backup cannot be restored at all →
  treat as a recoverability incident: escalate to the SRE Lead and follow RB-002 (Disaster
  Recovery). A backup that does not restore is a **high-severity** finding.
- Repeated drill failures for the same store → raise with the Tech Lead and re-validate the backup
  mechanism in `docs/sre/backup-recovery.md`.
