# Autonomy Boundaries — HITL / HOTL Definitions

**Owner:** AI Governance Lead + Security Lead
**Last reviewed:** 2026-05-24 | **Review cadence:** Quarterly

---

## Purpose

This document defines exactly which agent actions require human approval before
execution (HITL) and which may run autonomously under human monitoring (HOTL).
These boundaries are binding on all agent implementations in `src/agents/`.

---

## HITL — Requires Human Approval Before Execution

The following action categories **always** route through `src/agents/hitl_gateway.py`
and are blocked until a human approves or the request expires.

| Action category                      | Examples                                                      | Rationale                                       |
| ------------------------------------ | ------------------------------------------------------------- | ----------------------------------------------- |
| Write to production data stores      | Create, update, delete records                                | Irreversible; data integrity risk               |
| External API calls with side effects | Payment processing, notifications, provisioning               | Real-world effect outside system boundary       |
| Bulk operations                      | Actions affecting > `MAX_RECORDS_AFFECTED` rows               | Blast radius too large for autonomous execution |
| Actions rated HIGH or CRITICAL risk  | Scored by risk scorer before Act step                         | Risk threshold exceeded                         |
| Actions outside documented scope     | Action type not in agent's `allowed_action_types`             | Scope violation                                 |
| Cross-environment actions            | Any action targeting production from a non-production context | Environment boundary violation                  |

**Approval timeout:** `HITL_APPROVAL_TIMEOUT_SECONDS` (configured in `.env`).
Expired requests are **rejected** — never auto-approved. The requesting agent must
resubmit if the action is still needed.

**Approval interface:**

- `POST /v1/hitl/requests/{id}/approve` — approver records decision and rationale
- `POST /v1/hitl/requests/{id}/reject` — approver records rejection reason

---

## HOTL — Autonomous with Human Monitoring

The following action categories execute autonomously. A human monitors via the
ops dashboard and retains override capability at all times.

| Action category            | Examples                                        | Override mechanism               |
| -------------------------- | ----------------------------------------------- | -------------------------------- |
| Read-only data retrieval   | Document lookup, record fetch                   | Ops dashboard; stop agent        |
| Internal classification    | Risk scoring, intent classification             | Override classification result   |
| Draft generation           | Producing text for human review before delivery | Review and edit before delivery  |
| Metric collection          | Aggregating system metrics                      | N/A                              |
| Internal routing decisions | Task routing between agents                     | Override routing in orchestrator |

---

## Escalation Rules — HOTL → HITL

A HOTL flow automatically escalates to HITL when any of the following is true:

| Condition                                  | Threshold                       | Action                           |
| ------------------------------------------ | ------------------------------- | -------------------------------- |
| Anomaly score on input                     | > 0.7                           | Pause agent; create HITL request |
| Consecutive agent errors                   | ≥ 3 in 5 minutes                | Pause agent; create HITL request |
| Novel input category detected              | Classification confidence < 0.5 | Pause agent; create HITL request |
| Requested action not in known action types | Any unknown action type         | Reject; alert on-call            |

---

## Per-Agent Configuration

Each agent defines its own autonomy configuration in `src/shared/config.py`:

```python
# Example agent configuration
AGENT_ALLOWED_ACTION_TYPES = ["read_document", "summarise", "classify"]
AGENT_MAX_RECORDS_AFFECTED  = 10
AGENT_RISK_THRESHOLD_HITL   = 0.6   # above this score → HITL
```

Changes to an agent's allowed action types require: PR + Security Lead review + ADR update.

---

## Audit Requirements

Every HITL and HOTL decision is logged via `src/guardrails/audit_logger.py`:

| Event                | Fields logged                                                     |
| -------------------- | ----------------------------------------------------------------- |
| HITL request created | request_id, agent_id, action_type, risk_score, timestamp          |
| HITL approved        | request_id, approver_id (anonymised), rationale, timestamp        |
| HITL rejected        | request_id, approver_id (anonymised), rejection_reason, timestamp |
| HITL expired         | request_id, timestamp                                             |
| HOTL escalation      | agent_id, trigger_condition, escalation_target, timestamp         |

Audit records are immutable and retained for 1 year per ADR-0013.

---

## Quarterly Review

The AI Governance Lead and DPO review these boundaries each quarter:

- Have any new action types been added that are not yet classified?
- Have any incidents occurred that suggest a boundary needs tightening?
- Are HITL rejection rates within expected ranges?
- EU AI Act Art. 14 compliance confirmed?
