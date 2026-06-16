# ADR-0082 — Consolidated Backup RPO/RTO and Verified Restore Drills

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** SRE Lead (with DPO)
**Spec:** N/A — operational policy
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0062](ADR-0062-aurora-postgresql-platform-rdbms.md), [ADR-0067](ADR-0067-redis-as-timeseries-store.md), [ADR-0017](ADR-0017-agent-memory-architecture.md), [ADR-0075](ADR-0075-resilience-fallback-policy.md), [ADR-0026](ADR-0026-sox-audit-log-immutability.md)

> **Update (2026-06-16):** the "scheduled" half of this decision is now wired —
> `.github/workflows/restore-drill.yml` runs the drill weekly (Monday 06:23 UTC) for all three
> stores in `--dry-run` mode (also `workflow_dispatch` + on PRs touching the script). The decision
> below is unchanged; the drill stays inert (`--execute` still refused) until wired to real backups —
> the schedule keeps it runnable and the cadence visible.

> Copy this file to `docs/adr/ADR-NNNN-<kebab-title>.md`, fill every field, then add a row to the
> master index in `docs/adr/README.md`. ADRs are **append-only and immutable** (ADR-0059).

---

## Context

Recovery objectives and backup mechanics are documented today, but they are **scattered and the
verification loop is not closed**:

- Per-component RTO/RPO lives in `docs/resilience/dr-plan.md` (the governance view) and is
  authoritative in the executable procedure `docs/runbooks/disaster-recovery.md` (RB-002).
- Backup mechanism/retention per store lives in `docs/resilience/backup-restore-policy.md`, which
  itself consolidates `specs/privacy/data-retention.md` and
  `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md`.
- The agent-memory stores (semantic memory + bug history on **PostgreSQL + pgvector**, and the
  **Redis** session cache) are governed in `docs/ai/memory-governance.md` and ADR-0017, but their
  recovery objectives are only implied (they inherit the Aurora and Redis objectives).

The result is that an on-call engineer or auditor has **no single per-store table** answering
"what is the RPO, the RTO, the backup mechanism, and the restore pointer for _this_ store?", and —
more importantly — `backup-restore-policy.md` itself records two open gaps: there is **no scripted
restore**, **no `backup_last_success_timestamp` freshness alert**, and the drill-evidence folder
`docs/resilience/restore-drills/` **does not exist**. A backup that has never been restored is not
a proven backup; today nothing forces that proof on a schedule. This is an ISO 27001 control gap
(A.5.29/A.5.30 — see `skills/compliance/iso27001-change-management.md`).

## Decision

We will treat **a backup as "done" only when a restore of it has been proven on a schedule**, and
we will consolidate the recovery objectives so they have one first-class home.

Concretely:

1. **One consolidated, first-class doc** — `docs/sre/backup-recovery.md` — owns the single
   **per-store RPO/RTO/mechanism/cadence/restore-pointer table** for the stateful stores
   (PostgreSQL/Aurora, Redis session, Redis time-series, pgvector). It **cross-links** `dr-plan.md`
   and `backup-restore-policy.md` rather than restating them; those remain authoritative for the
   DR governance view and the backup retention policy respectively. Where the table and
   `dr-plan.md` overlap, `dr-plan.md` / RB-002 remain authoritative for the numbers and this doc
   mirrors them with a back-link.

2. **A scheduled, evidence-producing restore drill.** A restore drill runs on a fixed cadence
   (monthly per the existing backup-restore policy), restores the latest backup into a **scratch,
   throwaway** store, verifies integrity (row counts / a known key / `alembic current`), and
   records a dated evidence file under `docs/resilience/restore-drills/YYYY-MM-DD.md`. The drill is
   **pass/fail**: a failed or skipped drill pages SRE. Runbook **RB-SRE-006** documents how to run
   it and record evidence.

3. **A restore-drill automation scaffold** — `scripts/backup/restore_drill.sh` — that codifies the
   drill steps. It ships as a **non-destructive, `--dry-run`-by-default stub** to be wired to real
   backups later; it never touches the live/prod stores.

4. **A backup-freshness alert concept** — `backup_last_success_timestamp` — so a stale or missing
   backup pages SRE independently of the drill (closing the second gap in
   `backup-restore-policy.md`).

This ADR records the _policy and the closing of the verification loop_; it does not by itself wire
the automation to real infrastructure (that remains a tracked target-state item).

## Consequences

### Positive

- One canonical per-store recovery table — on-call and auditors stop reconstructing objectives from
  three documents.
- The verification loop is closed by construction: a restore that is never exercised now fails a
  scheduled, evidenced gate instead of being silently assumed to work.
- ISO 27001 A.5.29/A.5.30 evidence becomes a dated, append-only trail under
  `docs/resilience/restore-drills/`.
- The freshness alert and the drill are independent signals (a fresh backup that won't restore, and
  a restore script that works against a stale backup, are both caught).

### Negative / Trade-offs

- A new doc to keep in sync: if RTO/RPO change in `dr-plan.md`/RB-002, the consolidated table must
  be updated too. Mitigated by making `dr-plan.md`/RB-002 authoritative and cross-linking, not
  forking, the numbers.
- The automation ships inert (dry-run stub). Until it is wired to real backups, the drill is still a
  documented manual procedure — the stub reduces, but does not remove, manual effort.
- A scheduled drill consumes a scratch environment and operator time monthly.

### Neutral

- pgvector has no independent recovery objective: as a Postgres extension co-located in the Aurora
  cluster (ADR-0017), its RPO/RTO follow PostgreSQL/Aurora. The consolidated table records this
  explicitly rather than inventing separate numbers.

## Alternatives Considered

- **Do nothing / keep objectives scattered.** Rejected: leaves the unproven-backup gap open and the
  on-call lookup spread across three docs.
- **Put the consolidated table in `dr-plan.md`.** Rejected: `dr-plan.md` is deliberately the
  _governance_ view that points to RB-002 and does not restate procedure; a per-store
  backup/restore table is a distinct concern that belongs with the backup policy, not the DR
  governance plan. A dedicated SRE doc keeps each document single-purpose.
- **Wire the automation to real backups now.** Rejected for this ADR: a script that restores real
  backups is a high-blast-radius change needing its own spec, IAM scoping, and staging proof.
  Shipping an inert, dry-run scaffold first lets the runbook and evidence convention land safely.

## Compliance & Risk

- **Controls affected:** none of the OWASP ASVS/GenAI matrix controls change; this is an
  availability/recoverability control (ISO 27001 A.5.29 "ICT readiness for business continuity",
  A.5.30) — `skills/compliance/iso27001-change-management.md`.
- **Data classification impact:** none. Restored data retains its original classification and PII
  caps (`docs/data/data-classification.md`); the drill uses a throwaway store and must not export
  PII into evidence files (record counts/hashes, never raw rows).
- **Autonomy impact:** none — no HITL/HOTL behaviour or feature flag changes (ADR-0015).
- **Review/expiry:** permanent; re-validated each quarter with the DR plan review.

---

## Related

- `docs/sre/backup-recovery.md` — the consolidated per-store recovery doc this ADR establishes
- `docs/resilience/dr-plan.md` · `docs/resilience/backup-restore-policy.md`
- `docs/resilience/restore-drills/README.md` — drill evidence convention
- `docs/sre/runbooks/RB-SRE-006-restore-drill.md` — drill procedure
- `scripts/backup/restore_drill.sh` — automation scaffold (dry-run stub)
- `docs/adr/README.md` — master index & lifecycle definition
