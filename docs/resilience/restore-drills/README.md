# Restore-drill evidence

> **Owner:** SRE Lead | **Status:** Living evidence folder
> Append-only evidence that backups have been **proven by restore** on a schedule (ADR-0082).
> A backup that has never been restored is not a proven backup.

Each monthly restore drill (see `docs/sre/runbooks/RB-SRE-006-restore-drill.md` and the policy in
`docs/sre/backup-recovery.md` § Restore-drill verification) produces **one dated file** here.

## File naming

```
docs/resilience/restore-drills/YYYY-MM-DD.md
```

One file per drill, named for the drill date. Files are **append-only** — never edit or delete a
past record (it is ISO 27001 A.5.29/A.5.30 evidence). If a drill is re-run after a failure, add a
new dated file (or a new section in the same day's file noting the re-run).

## What a record must contain

Record **counts, hashes, and outcomes — never raw rows or PII**. The scratch store and its data are
destroyed after the drill; only the metadata below is retained.

| Field            | Meaning                                                                |
| ---------------- | ---------------------------------------------------------------------- |
| Date / drill ID  | When the drill ran; an identifier if you run more than one in a day    |
| Store(s)         | Which store(s) were restored (e.g. PostgreSQL/Aurora, Redis session)   |
| Backup restored  | Snapshot/PITR identifier + its timestamp (the backup's age at restore) |
| Scratch target   | The throwaway store identifier restored into (never live/prod)         |
| Integrity result | Row-count bounds OK? canary key present? `alembic current` == head?    |
| RTO achieved     | Wall-clock restore time, compared to the documented RTO for that store |
| Result           | **PASS** / **FAIL** (+ link to incident issue if FAIL)                 |
| Issues / notes   | Anything that slowed the restore or needs follow-up                    |
| Owner            | Who ran the drill                                                      |

## Template (copy into a new `YYYY-MM-DD.md`)

```markdown
# Restore drill — YYYY-MM-DD

- **Store(s):** <e.g. PostgreSQL (Aurora)>
- **Backup restored:** <snapshot/PITR id> (backup taken YYYY-MM-DDThh:mmZ — age <Nh>)
- **Scratch target:** <throwaway cluster/node id — NOT live/prod>
- **Integrity:** row-count bounds <OK/FAIL>; canary key <present/absent>; `alembic current` <head/mismatch>
- **RTO achieved:** <Nm> (documented RTO for this store: <Nm>) — <within / EXCEEDED>
- **Result:** PASS | FAIL <if FAIL: link to #<incident-issue>>
- **Issues / notes:** <none | ...>
- **Owner:** <name>
```

> No drill record is committed here yet — this folder is seeded by ADR-0082 ahead of the first
> scheduled drill. Do **not** fabricate a drill record; the first real file lands when the first
> drill runs.

## Related

- `docs/sre/backup-recovery.md` — consolidated recovery objectives + drill policy
- `docs/sre/runbooks/RB-SRE-006-restore-drill.md` — how to run a drill
- `docs/resilience/backup-restore-policy.md` · `docs/resilience/dr-plan.md`
- ADR-0082 — establishes this evidence convention
