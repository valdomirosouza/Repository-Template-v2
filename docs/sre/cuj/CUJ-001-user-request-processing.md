# CUJ-001 — User Request Processing

**CUJ ID:** CUJ-001
**Owner:** SRE Lead | **Last reviewed:** 2026-05-24

---

## User Role and Goal

**Role:** Authenticated end user
**Goal:** Submit a request to the system and receive a processed response within
the defined latency SLO, with confidence that any agent actions affecting their
data were reviewed by a human before execution.

---

## SLO Targets

| Signal                    | Target                                      | Window |
| ------------------------- | ------------------------------------------- | ------ |
| Availability              | ≥ 99.9% of requests return non-5xx response | 30d    |
| Latency p99               | ≤ 500ms end-to-end for read/classify flows  | 30d    |
| HITL approval latency p99 | ≤ 300s from request submission to decision  | 30d    |

---

## Step-by-Step Happy Path

```
1. User submits request via REST API (POST /v1/requests)
   → API gateway authenticates and rate-limits
   → Request ID returned immediately (202 Accepted)

2. Request published to broker as domain.created event
   → Event consumer picks up and routes to agent service

3. Agent service processes request (Perception → Reason → Act loop)
   → PII filter applied before LLM call
   → LLM inference generates proposed action

4. Risk scorer evaluates proposed action
   → Score < threshold → HOTL (agent executes autonomously)
   → Score ≥ threshold → HITL (HITL gateway creates approval request)

5a. HOTL path:
    → Agent executes action
    → Result published as domain.completed event
    → User notified (async)

5b. HITL path:
    → Human reviewer receives approval request (UI / notification)
    → Reviewer approves or rejects within SLO window (≤ 300s p99)
    → If approved: agent executes action → result published
    → If rejected: user notified with reason
    → If expired: request rejected automatically

6. Audit log entry written for all actions (HITL and HOTL)

7. User polls GET /v1/requests/{id}/status or receives webhook notification
   → Response contains result or status (pending_hitl / completed / rejected)
```

---

## Grafana Dashboard

`infrastructure/monitoring/grafana/dashboards/cuj-dashboards/cuj-001.json`

Panels:

- Request submission rate (requests/s)
- End-to-end p99 latency
- HITL approval queue depth
- HITL approval latency distribution
- Error rate by step

---

## Dependencies

| Dependency    | Type                  | Impact if unavailable            |
| ------------- | --------------------- | -------------------------------- |
| API gateway   | Upstream              | Total CUJ failure                |
| Kafka broker  | Async                 | Request queued; degraded latency |
| Agent service | Core                  | No processing                    |
| LLM provider  | External              | Agent fallback or failure        |
| HITL gateway  | Core (for HITL flows) | HITL requests blocked            |
| Audit logger  | Required              | Action blocked if write fails    |

---

## Failure Scenarios

| Scenario                   | Trigger                         | Expected degradation                                           | Recovery action                                        |
| -------------------------- | ------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------ |
| LLM provider timeout       | Provider latency spike          | Retry with backoff (max 3); return 503 with retry-after header | Monitor `llm_call_latency`; alert on-call if p99 > 10s |
| HITL approval timeout      | No reviewer responds within SLO | Request auto-rejected; user notified                           | Alert on-call; check reviewer availability             |
| Kafka consumer lag spike   | Consumer falls behind           | Increased end-to-end latency; no data loss                     | Scale consumer replicas; check DLQ                     |
| Audit logger write failure | Storage unavailable             | Action blocked; error returned to user                         | P1 incident; restore storage; replay from queue        |
| Agent service pod failure  | OOM or crash                    | Kubernetes restarts pod; brief unavailability                  | HPA scales replacement; alert if > 1 pod fails         |

---

## Test Coverage

| Test type          | File                                     | What it validates                      |
| ------------------ | ---------------------------------------- | -------------------------------------- |
| E2E happy path     | `tests/e2e/test_request_lifecycle.py`    | Full flow from submission to result    |
| HITL approval flow | `tests/e2e/test_hitl_approval_flow.py`   | Approval, rejection, and timeout paths |
| Integration        | `tests/integration/test_hitl_gateway.py` | HITL gateway approval mechanics        |
| Performance        | `tests/performance/k6/load-test.js`      | Latency under representative load      |
