# Skill — Incident Response

**Owner:** SRE Lead | **Reviewer:** Tech Lead | **Status:** Active | **Last updated:** 2026-05-28

Activate this skill when responding to a production alert, managing an active incident,
or writing a postmortem.

**Related:** `skills/sre/golden-signals.md`, `docs/runbooks/rollback-procedure.md`,
`docs/runbooks/disaster-recovery.md`, `docs/postmortems/POSTMORTEM-TEMPLATE.md`

---

## Severity Levels

| Level  | Definition                                   | Response SLA                      | Examples                                             |
| ------ | -------------------------------------------- | --------------------------------- | ---------------------------------------------------- |
| **P0** | Service unavailable for all users            | Page immediately; respond < 5 min | Zero request rate; critical error rate >5%           |
| **P1** | Significant degradation affecting many users | Page on-call; respond < 15 min    | p99 latency >2s; HITL queue stalled                  |
| **P2** | Minor degradation or single-user impact      | Ticket; respond < 4 h             | Elevated warning alerts; non-critical feature broken |
| **P3** | No user impact; operational concern          | Ticket; respond next business day | Approaching budget threshold; minor config drift     |

---

## Incident Lifecycle

```
Alert fires → Acknowledge → Triage → Mitigate → Resolve → Postmortem
```

### 1. Acknowledge (< 5 min for P0/P1)

- Acknowledge the alert in PagerDuty / on-call tool
- Post in the incident channel: `🔴 P{N} INCIDENT — [brief description] — I'm on it`
- If P0: immediately page Engineering Manager

### 2. Triage (< 15 min)

Follow the Golden Signals checklist in `skills/sre/golden-signals.md`:

1. Traffic — normal, zero, or spike?
2. Error rate — what percentage of requests are failing?
3. Saturation — CPU, memory, Kafka lag, semaphore waiting?
4. Latency — p50/p95/p99 vs baseline?

Then ask:

- Did this coincide with a recent deploy? (`helm history app -n production`)
- Is there a downstream dependency degraded? (LLM provider status page, DB latency)
- Is it isolated to one availability zone or pod?

### 3. Mitigate

**Fix forward** when: root cause is clear, fix takes < 15 min, rollback is riskier than the fix.

**Rollback** when: root cause is unclear, degradation is severe, or fix takes > 15 min.

```bash
# Rollback via Helm (preferred)
make rollback

# Emergency: disable autonomous actions via feature flag
# Set autonomous-mode flag to false in infrastructure/feature-flags/flags/autonomous-mode.yaml
# flagd will pick up the change within 30 s (hot-reload)
```

For HITL-specific incidents: `docs/runbooks/RB-003-hitl-recovery.md`

### 4. Resolve

- Confirm Golden Signals are back to baseline for ≥ 15 minutes
- Close the incident channel thread: `✅ RESOLVED — [brief description of fix]`
- Update the deployment environment status in GitHub

### 5. Postmortem

**Required for all P0 and P1 incidents.** Target: within 48 hours of resolution.

Template: `docs/postmortems/POSTMORTEM-TEMPLATE.md`

Mandatory sections:

- **Timeline** — when did the incident start, when detected, when resolved?
- **Root cause** — what actually caused it? (not "human error" — what systemic gap allowed it?)
- **Impact** — how many users affected, for how long?
- **Detection** — how was it discovered? Was the alert appropriate?
- **Action items** — concrete follow-ups with owners and due dates

Blameless principle: postmortems identify system and process gaps, not individual fault.

---

## HITL-Specific Incidents

When the HITL queue is stalled or operators cannot approve:

1. Check `hitl_active_requests` gauge — is the queue growing?
2. Check `HITLNoApprovals` alert — has it fired?
3. Check Redis connectivity — HITL store falls back to in-memory only in dev; production
   requires Redis (`docs/runbooks/RB-003-hitl-recovery.md`)
4. If operators are unavailable: escalate to Engineering Manager to authorise temporary
   feature flag change (`autonomous-mode-read-only`) to pause new HITL submissions

---

## Communication Templates

**Incident declared (post in #incidents):**

```
🔴 P{N} INCIDENT — {service} — {one-line description}
Started: {time}
On-call: {name}
Status: Investigating
```

**Update every 15 min during active P0/P1:**

```
📊 UPDATE — {time}
Status: {Investigating / Mitigating / Monitoring}
Current state: {what you know}
Next action: {what you're doing next}
ETA: {estimate or "unknown"}
```

**Resolution:**

```
✅ RESOLVED — {time}
Duration: {X} minutes
Root cause: {one sentence}
Fix: {one sentence}
Postmortem: {link or "to follow within 48h"}
```
