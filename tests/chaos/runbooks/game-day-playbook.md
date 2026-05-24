# Game Day Playbook — Chaos Engineering

**Runbook ID:** CHAOS-001
**Owner:** SRE Lead
**Last reviewed:** 2026-05-24

---

## Purpose

Validate system resilience through controlled failure injection in the staging environment. Game days build confidence that the system recovers automatically, alerts fire correctly, and the HITL/HOTL flow remains intact under failure conditions.

---

## Schedule

Weekly automated game days run via `.github/workflows/chaos-schedule.yml`.
Quarterly full-team game days rotate through all five scenarios from `docs/runbooks/disaster-recovery.md`.

---

## Participants

| Role                 | Responsibility                                              |
| -------------------- | ----------------------------------------------------------- |
| SRE Lead             | Facilitator; declares pass/fail; owns post-game-day actions |
| On-call engineer     | Executes experiments; monitors dashboards                   |
| Tech Lead (optional) | Observes; reviews findings for architecture improvements    |

---

## Pre-Game-Day Checklist

Before injecting any fault:

- [ ] Staging environment healthy — all Golden Signals green for 10+ minutes
- [ ] Baseline metrics captured: error rate, p99 latency, Kafka consumer lag
- [ ] Rollback procedure reviewed (`docs/runbooks/rollback-procedure.md`)
- [ ] HITL gateway confirmed operational — at least one test approval processed
- [ ] Incident channel open and participants confirmed
- [ ] Stakeholders notified that staging will be intentionally degraded

---

## Experiment Catalogue

| Experiment        | File                                             | Target         | Expected Behaviour                                                                                                 |
| ----------------- | ------------------------------------------------ | -------------- | ------------------------------------------------------------------------------------------------------------------ |
| Kill agent pod    | `tests/chaos/experiments/kill-agent.yaml`        | Agent service  | HITL queue drains; pending approvals preserved in store; service restarts and recovers within RTO (15 min)         |
| Network partition | `tests/chaos/experiments/network-partition.yaml` | Agent ↔ Broker | Circuit breaker activates; DLQ receives undelivered events; consumer lag spike then recovery; no data loss         |
| Broker outage     | `tests/chaos/experiments/broker-outage.yaml`     | Kafka          | Producers buffer with `max.block.ms`; consumers pause gracefully; full replay on recovery; no duplicate processing |

---

## Execution Steps (Per Experiment)

1. **Confirm staging is healthy** — check Golden Signals dashboard (golden-signals.json)
2. **Capture baseline metrics** — note error rate, p99 latency, consumer lag
3. **Start experiment** via Litmus / Chaos Toolkit:
   ```bash
   chaos run tests/chaos/experiments/<experiment>.yaml
   ```
4. **Monitor Golden Signals** — observe deviation from baseline
5. **Record observations:**
   - Time to detection (alert fired at T+?)
   - Time to recovery (service healthy again at T+?)
   - Any data loss detected?
   - HITL queue state after recovery
6. **Stop experiment** (if not self-terminating):
   ```bash
   chaos terminate tests/chaos/experiments/<experiment>.yaml
   ```
7. **Verify full recovery** — Golden Signals back to baseline for 5+ minutes
8. **Document findings** in `docs/postmortems/YYYY-MM-DD-game-day-<scenario>.md`

---

## Pass Criteria

All of the following must be true for a game day to PASS:

- [ ] RTO met: service recovered within the target RTO (see `docs/runbooks/disaster-recovery.md`)
- [ ] No data loss: all events produced before fault injection were consumed after recovery
- [ ] HITL approvals preserved: pending HITL requests survived the fault without auto-approval
- [ ] Audit log intact: all pre-fault audit records present; no corruption
- [ ] Automated alerts fired within **2 minutes** of fault injection
- [ ] DLQ depth returned to zero after recovery

---

## Fail Criteria

The game day FAILS if any of the following occur:

- RTO exceeded
- Data loss detected (events missing from consumer after recovery)
- HITL request auto-approved on timeout during fault (this must never happen)
- Audit log corrupted or records missing
- Automated alerts did not fire within 2 minutes
- DLQ messages not replayed after recovery

---

## Post-Game-Day Actions

After every game day, regardless of pass/fail:

1. Document the full timeline and findings in `docs/postmortems/`
2. File GitHub issues for any resilience gaps discovered
3. If fail criteria triggered: schedule follow-up game day within 2 weeks
4. Update runbooks with any new learnings
5. Update experiment YAML files if fault parameters need tuning
6. SRE Lead sends findings summary to Engineering Manager within 24 hours
