# On-Call Schedule Template

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** SRE Lead
> **Related:** `skills/sre/incident-response.md` · `docs/runbooks/` · `docs/sre/slo/slo.yaml`

This document defines the on-call rotation structure, escalation policy, paging rules,
and handoff procedure. Replace the placeholder values with your team's actual configuration
before going live.

---

## 1. Rotation Structure

### Primary On-Call

| Field              | Value                                                                  |
| ------------------ | ---------------------------------------------------------------------- |
| Rotation cadence   | Weekly (Mon 09:00 → Mon 09:00 local time)                              |
| Coverage hours     | 24 / 7                                                                 |
| Minimum rest       | 8 hours off between pages before escalating to secondary               |
| Eligible engineers | All engineers who have completed the on-call onboarding checklist (§7) |
| Schedule tool      | PagerDuty / Opsgenie / VictorOps _(replace with your tool)_            |

### Secondary On-Call (Escalation Tier)

| Field            | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| Rotation cadence | Weekly, offset by 3 days from primary                        |
| Role             | Escalation target if primary does not acknowledge within SLA |
| Eligible         | Senior engineers + SRE Lead                                  |

### On-Call Manager

| Field    | Value                                                            |
| -------- | ---------------------------------------------------------------- |
| Coverage | Business hours (Mon–Fri 09:00–18:00)                             |
| Role     | Escalation target for P0 incidents and stakeholder communication |
| Person   | Engineering Manager (permanent — not rotated)                    |

---

## 2. Escalation Policy

Escalation triggers automatically in the paging tool if the current tier does not acknowledge within the window.

```
Alert fires
  └── Primary on-call paged
        ├── Acknowledged within SLA → Primary owns the incident
        └── NOT acknowledged
              └── Secondary on-call paged (+5 min for P0/P1, +15 min for P2)
                    ├── Acknowledged → Secondary owns; primary informed
                    └── NOT acknowledged
                          └── Engineering Manager paged (+10 min for P0/P1)
                                └── P0 only: Tech Lead + SRE Lead paged simultaneously
```

### Acknowledgement SLAs

| Severity | Acknowledge within | Page secondary if not ack'd     |
| -------- | ------------------ | ------------------------------- |
| P0       | 5 min              | Immediately after 5 min         |
| P1       | 15 min             | After 15 min                    |
| P2       | 4 h                | After 4 h (business hours only) |
| P3       | Next business day  | Not escalated automatically     |

---

## 3. Paging Rules

Paging rules are configured in `infrastructure/monitoring/alertmanager/alertmanager.yml`. The table below maps Prometheus alert severity to paging behaviour.

| Alert severity | Routing                          | Channel                                         | Time restriction              |
| -------------- | -------------------------------- | ----------------------------------------------- | ----------------------------- |
| `critical`     | Page primary on-call immediately | PagerDuty high-urgency                          | None (24/7)                   |
| `warning`      | Notify primary on-call           | Slack `#alerts-warning` + PagerDuty low-urgency | Business hours only for P2/P3 |
| `info`         | Log only                         | Slack `#alerts-info`                            | None                          |

### Key Alert → Runbook Mapping

See `docs/runbooks/README.md` for the full alert → runbook index. Quick reference:

| Alert                    | Severity | Action                                                                   |
| ------------------------ | -------- | ------------------------------------------------------------------------ |
| `CriticalErrorRate`      | P1       | [RB-001 rollback-procedure](../runbooks/rollback-procedure.md)              |
| `AuditLogWriteFailure`   | P1       | [RB-003 hitl-recovery](../runbooks/RB-003-hitl-recovery.md)                 |
| `ConsumerLagCritical`    | P1       | [RB-005 kafka-consumer-lag](../runbooks/RB-005-kafka-consumer-lag.md)       |
| `CircuitBreakerOpen`     | P1       | [RB-004 db-connection-failure](../runbooks/RB-004-db-connection-failure.md) |
| `HITLQueueDepthCritical` | P1       | [RB-003 hitl-recovery](../runbooks/RB-003-hitl-recovery.md)                 |

---

## 4. On-Call Responsibilities

### During Shift

- [ ] Keep phone accessible and notifications enabled at all times.
- [ ] Acknowledge pages within the SLA (§2).
- [ ] For P0/P1: post in `#incidents` within 5 minutes of acknowledging.
- [ ] Follow the incident lifecycle: Acknowledge → Triage → Mitigate → Resolve → Postmortem.
- [ ] Use runbooks in `docs/runbooks/` — do not improvise for known failure modes.
- [ ] Keep the incident channel updated every 15 minutes during active P0/P1.
- [ ] For P0: notify Engineering Manager immediately; update status page.
- [ ] After resolution: open a postmortem ticket if P0 or P1 (see §6).

### Not Responsible For

- Feature development during on-call week (unless voluntary and quiet).
- Resolving issues outside the system boundary (third-party SaaS outages).
- Making breaking changes to production without CAB approval — even during incidents, use the emergency-change process (CLAUDE.md §11).

---

## 5. Handoff Procedure

Handoffs occur every Monday at 09:00. Both outgoing and incoming on-call engineers must participate.

### Outgoing Engineer Checklist

- [ ] Review all incidents from the past week; ensure postmortems are filed or scheduled.
- [ ] Document any known flaky alerts or ongoing investigations in the handoff note.
- [ ] Transfer ownership of any open P2/P3 incidents to the incoming engineer.
- [ ] Update on-call schedule tool to reflect the rotation.
- [ ] Send handoff note to `#on-call-handoff` Slack channel (template below).

### Incoming Engineer Checklist

- [ ] Read the handoff note from the outgoing engineer.
- [ ] Review `docs/sre/slo/slo.yaml` — check error budget remaining for each service.
- [ ] Confirm PagerDuty / alerting tool is configured to page your number.
- [ ] Review any open incidents or elevated alert states.
- [ ] Acknowledge the handoff in `#on-call-handoff`.

### Handoff Note Template

```
## On-Call Handoff — Week of YYYY-MM-DD

**Outgoing:** @handle
**Incoming:** @handle

### Incidents this week
- [INC-NNN] Brief description — resolved / postmortem filed / postmortem pending

### Known issues / watch items
- [Alert name] — context on why it's noisy / what to watch for

### Open P2/P3 tickets being transferred
- [TICKET-NNN] Description — current status

### Error budget status
- api-gateway: X% remaining (normal / at risk / exhausted)
- agent-service: X% remaining

### Notes for incoming engineer
- Any other context
```

---

## 6. Post-Incident Actions

| Severity | Postmortem required? | SLA to file            | Template                                  |
| -------- | -------------------- | ---------------------- | ----------------------------------------- |
| P0       | Yes — mandatory      | Within 48 hours        | `docs/postmortems/POSTMORTEM-TEMPLATE.md` |
| P1       | Yes — mandatory      | Within 5 business days | `docs/postmortems/POSTMORTEM-TEMPLATE.md` |
| P2       | Recommended          | Within 2 weeks         | Short-form postmortem or JIRA ticket      |
| P3       | No                   | —                      | Log in incident channel only              |

Postmortems are blameless — see `docs/runbooks/README.md` §Blameless Principles.

---

## 7. On-Call Onboarding Checklist

Complete before joining the primary rotation for the first time.

- [ ] Read `skills/sre/incident-response.md` — severity levels, incident lifecycle, communication templates.
- [ ] Read `docs/runbooks/README.md` — alert-to-runbook index and all six runbooks.
- [ ] Read `docs/sre/slo/slo.yaml` — understand the SLOs and error budget policy.
- [ ] Read `docs/sre/deployment-strategy.md` — understand rollback paths.
- [ ] Shadow a P1 or P0 incident (live or tabletop drill) with an experienced on-call engineer.
- [ ] Complete one full on-call week as secondary before becoming primary.
- [ ] Confirm paging tool (PagerDuty / Opsgenie) account is active and phone number verified.
- [ ] Join Slack channels: `#incidents`, `#alerts-warning`, `#on-call-handoff`.
- [ ] Pair with SRE Lead to review the Grafana Golden Signals dashboard.

---

## 8. On-Call Health and Sustainability

- **Maximum consecutive weeks:** 2 weeks primary on-call before a mandatory break week.
- **Minimum team size for rotation:** 4 engineers (ensures ≤ 25% on-call burden per person).
- **Night-time pages:** P0 and P1 only. P2/P3 alerts suppress to business hours (`inhibit_rules` in `alertmanager.yml`).
- **Incident retrospective:** If an engineer is paged more than 3 times in a single night, the SRE Lead reviews the alert for tuning or runbook improvement the next business day.
- **Time off:** On-call weeks may be swapped with advance notice (≥ 48 h) and confirmation from the swapping engineer. Update the schedule tool and notify `#on-call-handoff`.

---

## 9. Customisation Checklist

Before this template is production-ready for your organisation:

- [ ] Replace `PagerDuty / Opsgenie / VictorOps` with your actual paging tool and configure routing rules in `infrastructure/monitoring/alertmanager/alertmanager.yml`.
- [ ] Set real rotation cadence and eligible-engineer list in the paging tool.
- [ ] Verify Slack channel names match your workspace (`#incidents`, `#alerts-warning`, `#on-call-handoff`).
- [ ] Set Engineering Manager contact in §1.
- [ ] Calibrate minimum team size and consecutive-weeks limit to your team size (§8).
- [ ] Run a tabletop drill with the full team before going live.
