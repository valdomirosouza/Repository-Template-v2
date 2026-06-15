# ADR-0082 — Automated Restore-Drill Verification

**Status:** Proposed
**Date:** 2026-06-15
**Authors:** Valdomiro Souza
**Spec:** docs/resilience/backup-restore-policy.md (§Backup verification & drills), docs/resilience/dr-plan.md (§Drills, review & evidence)
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0062](ADR-0062-aurora-postgresql-platform-rdbms.md) (Aurora HA / PITR), [ADR-0075](ADR-0075-resilience-fallback-policy.md) (fallback policy), [ADR-0026](ADR-0026-sox-audit-log-immutability.md) (audit immutability)

## Context

Backup and recovery objectives are documented (`docs/runbooks/disaster-recovery.md` RB-002,
`docs/resilience/dr-plan.md`, `docs/resilience/backup-restore-policy.md`), and policy already
mandates a **monthly restore-to-throwaway + integrity check** with evidence recorded under
`docs/resilience/restore-drills/YYYY-MM-DD.md`. What is missing is **automation**: the restore
procedures are operator templates only, there is no scripted restore, and the monthly drill is a
manual exercise that depends on someone remembering to run it. The backup-restore policy itself
calls this out as a gap ("**No scripted restore** (`scripts/restore/`) yet — procedures manual").

A backup that is never restored is not a backup. To make the monthly verification dependable,
auditable, and cheap to run, the restore steps must become parameterised, idempotent-by-default
scripts that are safe to run in CI, and the drill itself must be orchestrated and evidenced
without manual transcription.

## Decision

1. **Scripted, parameterised restores.** Add `scripts/restore/` with one script per stateful
   store — `restore_aurora_pitr.sh` (Aurora point-in-time recovery), `restore_redis_snapshot.sh`
   (ElastiCache snapshot), `restore_kafka_snapshot.sh` (MSK snapshot). Each is driven entirely by
   environment variables (no hard-coded account/cluster identifiers), uses `set -euo pipefail`, is
   shellcheck-clean, and ships `--help`/usage. They restore to a **throwaway target** named per
   environment, never to a production resource.

2. **Dry-run is the default; destructive actions are opt-in.** Every script defaults to
   `--dry-run`: it prints the resolved restore plan (source, target, point-in-time, identifiers)
   and performs **no** AWS mutations. A real restore requires the explicit `--execute` flag. This
   makes the scripts safe to run in CI on every change and safe to reason about in review.

3. **Orchestrated drill with evidence.** `scripts/restore/run_restore_drill.sh` orchestrates a
   dry-run drill across all three stores and writes a dated evidence file from a template into
   `docs/resilience/restore-drills/YYYY-MM-DD.md`, matching the convention the policy already
   defines (what was restored, RTO achieved, integrity result, issues, owner). The evidence folder
   is created (with a `README.md` describing the convention and template) so the path exists.

4. **Scheduled CI drill restores to a throwaway env, verifies integrity, and pages SRE on
   failure.** The intended steady state is a **monthly scheduled** GitHub Actions workflow that
   provisions a throwaway environment, runs the scripts in `--execute` mode against it, runs
   integrity checks, commits the evidence file, and pages SRE if any step fails (wiring to the
   existing alert path). See "Follow-up" — the workflow itself is **not** added in this change.

## Follow-up (deferred — gated on an RFC)

Adding a `.github/workflows/*.yml` is **DevOps-owned** and requires an **RFC** under v2 change
governance (`skills/change-management/rfc-process.md`, ISO 27001 change management, ADR-0027).
This ADR therefore **deliberately scopes the workflow out**. The next step is:

- Raise an RFC for `backup-restore-verification.yml` (monthly `cron`) that: spins up a throwaway
  environment, runs `scripts/restore/run_restore_drill.sh --execute`, runs integrity checks,
  commits the evidence file to `docs/resilience/restore-drills/`, and pages SRE on failure.
- In the same RFC, wire the `backup_last_success_timestamp` metric and a stale-backup alert
  (>26h) into `infrastructure/monitoring/prometheus/rules/resilience-alerts.yaml`.

Until that RFC lands, the scripts are runnable manually (dry-run in CI, `--execute` in a
human-approved drill) and the monthly verification remains an operator procedure that now has
real tooling behind it.

## Consequences

### Positive

- The monthly restore verification becomes repeatable and auditable instead of ad hoc.
- Restore procedures are tested-as-code (dry-run in CI), closing the "no scripted restore" gap.
- Evidence is generated from a template, so drill records are consistent and complete.
- Safe by construction: dry-run default + throwaway-only targets mean no path to a prod mutation.

### Negative / trade-offs

- The scripts are skeletons over cloud CLIs; they must be kept in step with `SPEC-INFRA-001` and
  the actual Terraform-provisioned identifiers.
- Full value (unattended monthly verification, paging) is not realised until the deferred workflow
  RFC is approved and merged.

## Alternatives Considered

- **Keep restores as manual operator templates.** Rejected — leaves the policy's stated gap open
  and the monthly drill dependent on memory; backups stay unverified between drills.
- **Ship the scheduled workflow in this change.** Rejected — a workflow is DevOps-owned and needs
  an RFC (v2 governance). Splitting the ADR + scripts from the workflow keeps this change
  approvable without blocking on the RFC.
- **Continuous (per-deploy) restore verification.** Deferred — cost/time of a full restore makes
  monthly the right cadence; revisit if RPO/RTO tighten.

## Compliance & Risk

- **Controls affected:** ISO 27001 A.5.29/A.5.30 (continuity / ICT readiness) — verified recovery;
  ADR-0026 (audit immutability) — restored audit data must remain append-only.
- **Data classification impact:** restores may rehydrate L1/L2 PII into a throwaway env; that env
  inherits the same encryption + retention caps as production (`docs/data/data-classification.md`,
  ADR-0018/0019) and must be torn down after the drill.
- **Autonomy impact:** none — no `src/agents/` or `src/guardrails/` change; no AI-safety phase.
- **Review/expiry:** revisit once the deferred workflow RFC is merged (move Status → Accepted) and
  whenever per-service RPO/RTO change.

## Related

- `docs/resilience/backup-restore-policy.md` · `docs/resilience/dr-plan.md`
- `docs/runbooks/disaster-recovery.md` (RB-002) · `docs/sre/runbooks/README.md`
- `scripts/restore/` · `docs/resilience/restore-drills/README.md`
- `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md` · ADR-0062 · ADR-0075 · ADR-0027
