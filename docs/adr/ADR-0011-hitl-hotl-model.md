# ADR-0011 — HITL/HOTL Human Oversight Model

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** AI Lead, Security Lead

---

## Context

AI agents in this system can propose actions with real-world effects: writing to
data stores, calling external APIs, sending notifications, and provisioning resources.
Unreviewed autonomous execution of these actions carries legal, reputational, and
safety risk. EU AI Act Arts. 13–14 require deployed AI systems to support human
oversight and intervention mechanisms.

Two extremes are unacceptable:

- **Fully autonomous:** agents execute all actions without human review — unacceptable
  risk; non-compliant with EU AI Act Art. 14
- **Fully manual:** all agent outputs require human approval before any action —
  defeats the purpose of automation; operationally unsustainable

---

## Decision

Adopt a **two-tier oversight model**:

### Tier 1 — HITL (Human in the Loop)

Applied to: all actions with real-world effects (writes, external calls, notifications,
provisioning, any action affecting more than the configured record threshold).

- Agent proposes the action; execution is blocked until a human approves
- Implemented in `src/agents/hitl_gateway.py`
- Approval interface: REST endpoint `/v1/hitl/requests/{id}/approve` and `/reject`
- Timeout: requests expire after `HITL_APPROVAL_TIMEOUT_SECONDS`; expired requests
  are **rejected**, never auto-approved
- Every decision (approve / reject / expire) is logged immutably via `audit_logger.py`

### Tier 2 — HOTL (Human on the Loop)

Applied to: read-only operations, internal classification, draft generation,
metric collection — flows where the agent acts autonomously but a human monitors
with override capability at all times.

- Human override available via the ops dashboard at all times
- Automatic escalation to HITL if anomaly score exceeds threshold or error rate spikes
- Agent metrics visible in `infrastructure/monitoring/grafana/dashboards/golden-signals.json`

---

## Consequences

### Positive

- All consequential agent actions have a documented human decision in the audit trail
- EU AI Act Art. 14 compliance is structural, not procedural
- HOTL tier maintains automation throughput for low-risk operations
- Approval timeout prevents actions from lingering in an indefinitely pending state

### Negative / Trade-offs

- HITL flows introduce latency equal to human review time (SLO target: p99 ≤ 300s)
- Human reviewers must be trained on the approval interface and the action risk taxonomy
- HOTL monitoring requires disciplined alert routing; unmonitored HOTL flows defeat
  the oversight model

---

## Alternatives Considered

**Confidence-threshold auto-approval**
Rejected: LLM confidence scores are not calibrated to real-world risk; a high-confidence
incorrect action is worse than a low-confidence one that waits for review. Auto-approval
based on model output is incompatible with EU AI Act Art. 14.

**Post-hoc review (log and review after execution)**
Rejected: irreversible actions cannot be undone after the fact; this model does not
satisfy the "human oversight before execution" requirement of the EU AI Act.
