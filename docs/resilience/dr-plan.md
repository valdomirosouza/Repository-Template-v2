# Disaster Recovery Plan

> **Owner:** SRE Lead (with DPO for data-loss/compliance) | **Status:** Living plan
> The **executable procedure** is `docs/runbooks/disaster-recovery.md` (RB-002) — follow it during an
> actual event. This plan is the governance view: the recovery objectives, scope, review cadence, and
> compliance ties. It does not restate RB-002's steps; it points to them.

Baseline: **RTO ≤ 1h** (DORA Elite MTTR, `docs/sre/slo/slo.yaml`). Per-service objectives below are
tighter and authoritative in RB-002.

---

## Recovery objectives (RTO / RPO)

| Component         | RPO (max data loss)         | RTO (max downtime) | Recovery mechanism                               |
| ----------------- | --------------------------- | ------------------ | ------------------------------------------------ |
| api-gateway       | 0 (stateless)               | 5 min              | redeploy / scale (Helm)                          |
| agent-service     | 15 min                      | 15 min             | restart; Redis session restore; HITL preserved   |
| event-consumer    | 0 (Kafka replay)            | 10 min             | broker recovery + replay; DLQ drain              |
| Database (Aurora) | 1h (last backup) / PITR     | 30 min             | reader failover (~30s, ADR-0062) or PITR restore |
| Audit log         | 0 (append-only, replicated) | 15 min             | fail-closed; never InMemory in prod (ADR-0075)   |

## Scope — disaster scenarios (procedures in RB-002)

1. **Region / provider outage** → failover (multi-AZ Aurora; redeploy).
2. **Database corruption** → pause writes, restore from backup/PITR, validate (`docs/resilience/backup-restore-policy.md`).
3. **Kafka complete failure** → broker health-check, DLQ replay on recovery (`docs/sre/runbooks/dlq-accumulating.md`).
4. **LLM provider outage** → degraded/fallback mode via feature flags; circuit breaker opens (`src/shared/retry.py`).
5. **Security incident** → shutdown, key rotation, GDPR/LGPD 72h breach clock (`docs/sre/runbooks/db-key-rotation.md`).

## Dependency recovery order

1. Network / DNS / secrets (Vault) → 2. Aurora (writer) → 3. Redis → 4. Kafka (+ schema registry) →
2. api-gateway → 6. agent-service / event-consumer → 7. resume HITL queue draining.

Rationale: the audit log (fail-closed) and DB must be healthy before agents act, so the platform
never executes actions it cannot record (ADR-0075, ADR-0026).

## Activation & communications

- **Trigger / declare:** per RB-002 activation criteria; Incident Commander owns the call.
- **Comms:** escalation matrix in RB-002 (Engineering → SRE Lead → DPO → external status page).
- **Rollback path** for a bad release: `docs/runbooks/rollback-procedure.md` (RB-001) + `make rollback`.

## Drills, review & evidence

- **DR drills:** quarterly, rotating the five scenarios (RB-002); chaos game-days exercise the
  mechanisms weekly/quarterly (`tests/chaos/runbooks/game-day-playbook.md`).
- **Restore verification:** monthly restore-to-test + integrity check (see backup-restore policy).
- **Review cadence:** this plan + RB-002 reviewed each quarter and after any real incident; RTO/RPO
  re-validated against the SLO. Record drill outcomes as evidence (`docs/resilience/backup-restore-policy.md`
  → drill-evidence convention) and link post-mortems in `docs/postmortems/`.
- **Compliance:** DR is an ISO 27001 control (A.5.29/A.5.30) — see `skills/compliance/iso27001-change-management.md`.

---

## Related

- `docs/runbooks/disaster-recovery.md` (RB-002) — **authoritative procedure**
- `docs/resilience/backup-restore-policy.md` · `docs/resilience/chaos-experiment-catalog.md`
- ADR-0062 (Aurora HA) · ADR-0075 (fallback policy) · ADR-0026 (audit immutability)
- `docs/sre/slo/slo.yaml` — RTO/MTTR target
