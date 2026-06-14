# Resilience

> **Owner:** SRE Lead | **Status:** Living index
> Resilience is **already implemented** in this repo — in-memory fallbacks, circuit breakers, a DR
> runbook, and a chaos-experiment suite all exist. This directory is the **map and governance layer**
> over that material: it consolidates the scattered sources into navigable plans and links back to
> the authoritative implementations rather than duplicating them.

The baseline reliability target is **RTO ≤ 1h** (DORA Elite MTTR, `dora_mttr_target_seconds: 3600`
in `docs/sre/slo/slo.yaml`); per-service RTO/RPO are tighter (see the DR plan).

## Contents

| Doc                                                          | Purpose                                                         |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| [`dr-plan.md`](dr-plan.md)                                   | Consolidated DR plan: RTO/RPO matrix, scenarios, review cadence |
| [`backup-restore-policy.md`](backup-restore-policy.md)       | Backup retention, restore procedure templates, drill evidence   |
| [`chaos-experiment-catalog.md`](chaos-experiment-catalog.md) | The 10 chaos experiments with steady-state + pass/fail          |

## Sources of truth (this directory governs, does not replace)

- **DR runbook:** `docs/runbooks/disaster-recovery.md` (RB-002) — the operational procedure
- **Rollback:** `docs/runbooks/rollback-procedure.md` (RB-001) + `make rollback`
- **Fallback policy:** ADR-0075 (degrade-open vs fail-closed) — the classification rule
- **Chaos experiments:** `tests/chaos/experiments/*.yaml` + `tests/chaos/runbooks/game-day-playbook.md` (CHAOS-001)
- **Code:** `src/shared/retry.py` (circuit breaker + retry), in-memory fallbacks in `src/agents/`, `src/shared/broker.py`, `src/guardrails/audit_logger.py`
- **Infra backups:** `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md`, ADR-0062 (Aurora HA)
- **Alerts:** `infrastructure/monitoring/prometheus/rules/resilience-alerts.yaml`

## Related

- `skills/sre/incident-response.md` · `skills/change-management/deploy-rollback.md`
- `docs/runbooks/README.md` — runbook namespaces (ADR-0033)
- `docs/governance/traceability-matrix.md`
