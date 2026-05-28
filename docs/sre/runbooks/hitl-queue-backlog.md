# Runbook: HITL Queue Backlog

**Owner:** SRE Lead | **Reviewer:** AI Governance Lead | **Last updated:** 2026-05-28
**Alerts:** `HITLQueueDepthHigh` (>50 pending, 5 min) · `HITLNoApprovals` (0 approvals in 30 min with >5 pending)
**SLO reference:** `docs/sre/slo/slo.yaml` → `hitl-system.hitl_decision_latency_p95`, `hitl-system.hitl_queue_depth`
**Dashboard:** `infrastructure/monitoring/grafana/dashboards/agent-supervision.json`
**Governance:** All HITL interventions must be logged in the audit trail.

---

## Severity Classification

| Queue depth | No approvals window | Severity | Impact                                                         |
| ----------- | ------------------- | -------- | -------------------------------------------------------------- |
| > 100       | Any                 | P1       | Agent pipeline stalled; user requests blocked at HITL boundary |
| 51–100      | > 30 min            | P1       | Operator throughput insufficient; SLO breach                   |
| 51–100      | < 30 min            | P2       | Elevated; monitor closely                                      |
| 10–50       | > 30 min            | P2       | Operator may be unavailable                                    |

---

## Step 1 — Assess the Backlog (< 3 minutes)

```bash
# Current queue depth
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(hitl_active_requests) by (agent_id)' \
  | python3 -m json.tool

# p90 wait time for pending requests
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.90, sum(rate(hitl_wait_seconds_bucket[10m])) by (agent_id, le))' \
  | python3 -m json.tool

# HITL status via API
curl -f http://localhost:8000/v1/hitl/status | python3 -m json.tool

# Approval/rejection rate in last 30 min
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(increase(hitl_approvals_total[30m])) + sum(increase(hitl_rejections_total[30m]))' \
  | python3 -m json.tool
```

---

## Step 2 — Determine Cause

### 2a. No operator available

**Symptom:** Zero approvals in >30 min with pending queue.

**Actions:**

1. Check the operator notification channel (Slack/PagerDuty).
2. Contact the on-call HITL operator directly.
3. Escalate to the HITL operator team lead if no response within 15 min.
4. Do **not** auto-approve requests to clear the queue — this violates ADR-0011.

### 2b. Operator portal unresponsive

```bash
# Check frontend pod health
kubectl get pods -n default -l app=frontend
kubectl logs -n default -l app=frontend --tail=50 | grep error

# Check api-gateway HITL endpoints
curl -f http://localhost:8000/v1/hitl/status
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{route="/v1/hitl/requests/{request_id}/decision",status=~"5.."}[5m]))' \
  | python3 -m json.tool
```

### 2c. Request flood from a single action_type

```bash
# Identify which action_type is flooding the queue
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(hitl_active_requests) by (action_type)' \
  | python3 -m json.tool
```

If one `action_type` dominates, consider disabling it via the feature flag to stem the flood while operators clear existing requests.

### 2d. Risk scorer sending too many actions to HITL

```bash
# Check autonomous resolution rate
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=agent_autonomous_resolution_rate' \
  | python3 -m json.tool

# Check feedback bias values
make agent-feedback-check
```

A sustained drop in autonomous resolution rate with a queue spike indicates the risk scorer thresholds are too conservative. This requires a governance review before any threshold change (ADR-0015).

---

## Step 3 — Drain Procedure

### 3a. Normal drain (operators work through queue)

The standard drain procedure is for operators to process requests in order via the HITL UI. Provide operators with:

1. The pending request count and oldest request age.
2. A sorting guide: process highest-risk or oldest requests first.
3. Confirm that the approval endpoint is healthy (`GET /v1/hitl/status`).

### 3b. Emergency drain via API (P1 — SRE + AI Governance Lead sign-off required)

Only execute this if: the queue is > 100, operators are unavailable, and agent requests are blocking user-facing SLOs.

```bash
# Reject the oldest N requests with a documented rationale
# GOVERNANCE REQUIREMENT: This action must be approved by AI Governance Lead first.
# Log the action in docs/postmortems/ before executing.

# Example: reject a specific pending request with a documented reason
curl -X POST http://localhost:8000/v1/hitl/requests/{REQUEST_ID}/decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "REJECTED",
    "rationale": "Emergency queue drain — P1 incident. Approved by AI Governance Lead. See postmortem docs/postmortems/YYYYMMDD-hitl-drain.md.",
    "approver_id": "sre-oncall-emergency"
  }'
```

**Important:** Every emergency rejection must be documented with `correlation_id`, timestamp, and governance approval reference. The audit log is immutable and will capture this.

### 3c. Stop the flood — disable an action_type

```bash
# Disable a specific action_type via feature flag (requires AI Governance Lead approval)
# Edit the relevant flag file and deploy:
# infrastructure/feature-flags/flags/autonomous-mode-{level}.yaml

# Verify the flag change takes effect
kubectl rollout restart deployment/api-gateway -n default
kubectl rollout status deployment/api-gateway -n default --timeout=60s
```

---

## Step 4 — Notify and Document

Immediately after any P1 HITL queue incident:

1. Notify AI Governance Lead (within 1 hour per ADR-0011 governance requirements).
2. If requests were auto-rejected during drain: notify affected users via the standard notification path.
3. File postmortem in `docs/postmortems/` within 48 hours.
4. Review `agent_autonomous_resolution_rate` in the next sprint — a recurring queue backlog indicates risk scorer recalibration is needed.

---

## Step 5 — Verify Recovery

```bash
# Queue depth should be trending down
watch -n 30 'curl -sG "http://localhost:9090/api/v1/query" \
  --data-urlencode "query=sum(hitl_active_requests)" | python3 -m json.tool'

# Approval rate should be > 0
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(increase(hitl_approvals_total[5m]))' \
  | python3 -m json.tool
```

---

## Escalation

| Condition                                 | Escalate to                    | Timeline          |
| ----------------------------------------- | ------------------------------ | ----------------- |
| Queue > 100 with no operators available   | AI Governance Lead             | Immediately       |
| Emergency drain required                  | AI Governance Lead + SRE Lead  | Before any action |
| Risk scorer causing systematic HITL flood | AI Governance Lead + Tech Lead | Within 2 h        |
| User SLOs breached due to HITL blocking   | Engineering Manager            | Within 1 h        |
