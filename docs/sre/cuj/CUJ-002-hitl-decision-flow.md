# CUJ-002 — HITL Decision Flow

**CUJ ID:** CUJ-002
**Owner:** SRE Lead | **Last reviewed:** 2026-05-28

---

## User Role and Goal

**Role:** HITL operator (authenticated reviewer with `hitl:operator` role)
**Goal:** Review a pending agent action request, understand the proposed action and its risk score, and submit an APPROVE or REJECT decision within the SLO window — with confidence that the decision is immediately effective and permanently audit-logged.

---

## SLO Targets

| Signal                    | Target                                             | Window |
| ------------------------- | -------------------------------------------------- | ------ |
| Decision latency p95      | ≤ 300 s from request creation to decision recorded | 30d    |
| HITL gateway availability | ≥ 99.9% of decision submissions return non-5xx     | 30d    |
| Queue depth               | ≤ 100 pending requests at any time                 | 30d    |
| Audit log write success   | 100% of decisions written to immutable audit log   | 30d    |

---

## Step-by-Step Happy Path

```
1. Operator opens HITL approval UI (frontend/frontend/)
   → Operator authenticates with OIDC/JWT
   → Frontend polls GET /v1/hitl/status (5 s interval)
   → Pending queue displayed with oldest requests first

2. Operator selects a pending request
   → Frontend calls GET /v1/requests/{id} for context
   → Displays: action_type, risk_score, masked_context_summary, expires_at

3. Operator reviews the request (reads context, assesses risk)
   → Confirms proposed action is within approved scope
   → Ensures rationale is documented (min 10 chars, max 1000 chars)

4. Operator submits decision
   → POST /v1/hitl/requests/{id}/decision
     { decision: "APPROVED" | "REJECTED", rationale: "...", approver_id: "..." }
   → API gateway records decision in HITLGateway
   → Decision written to immutable audit log (audit_logger.py)
   → Response: 200 DecisionOut within 200 ms p99

5. Agent receives decision (async)
   → APPROVED: agent executes action → publishes agent.action.approved
   → REJECTED: agent cancels action → publishes agent.action.rejected
   → Either outcome: user notified via domain.result.completed

6. Operator sees queue updated
   → Decided request disappears from pending queue on next poll
```

---

## Grafana Dashboard

`infrastructure/monitoring/grafana/dashboards/agent-supervision.json`

Key panels for this CUJ:

- Active HITL Queue depth (stat — alert threshold: 50)
- p90 HITL wait time (timeseries — SLO target: ≤ 300 s)
- Approval vs rejection rate by action_type (timeseries)
- Decision submission latency histogram (heatmap)
- Zero-approval alert indicator (stat — red when HITLNoApprovals fires)

---

## Dependencies

| Dependency               | Type          | Impact if unavailable                                                         |
| ------------------------ | ------------- | ----------------------------------------------------------------------------- |
| api-gateway `/v1/hitl/*` | Core          | Decision submission blocked                                                   |
| Redis HITLStore          | Core          | Pending state unavailable; pipeline stalls                                    |
| PostgreSQL audit log     | Required      | Decision blocked if write fails (invariant: no decision without audit record) |
| Frontend operator UI     | Operator path | Operators must fall back to direct API calls                                  |
| OIDC provider            | Auth          | Operators cannot authenticate; manual API fallback with service account       |

---

## Failure Scenarios

| Scenario                        | Trigger                                | Expected degradation                                                  | Recovery                                                               |
| ------------------------------- | -------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| No operator available           | Operator offline / unreachable         | Queue grows; requests expire (auto-rejected per ADR-0011)             | Page HITL operator team; see `docs/sre/runbooks/hitl-queue-backlog.md` |
| Redis unavailable               | Redis pod down                         | New HITL requests unqueueable; 503 to users                           | Restore Redis; see `docs/sre/runbooks/redis-connection-failure.md`     |
| Decision endpoint 5xx           | api-gateway degraded                   | Operator cannot submit; must retry                                    | `docs/sre/runbooks/api-gateway-high-error-rate.md`                     |
| Request expired before decision | Operator took > expiry window          | Auto-rejected; user notified; audit-logged                            | No recovery needed — by design (ADR-0011)                              |
| Audit log write failure         | PostgreSQL unavailable                 | Decision **blocked** — system refuses to execute without audit record | P1 incident; restore PostgreSQL immediately                            |
| Frontend polling fails          | Network partition or frontend pod down | Operator sees stale queue; can still submit via direct API            | Restart frontend pod; operators use `curl` fallback                    |

---

## SLO Degraded Path

When the decision latency p95 is trending above 250 s (warning level — 50 s before SLO breach):

1. Check queue depth: `GET /v1/hitl/status`
2. If queue > 50: initiate `docs/sre/runbooks/hitl-queue-backlog.md`
3. If queue is normal but latency is high: check operator portal performance (frontend pod, API response times)
4. If decision endpoint latency > 200 ms p99: treat as API degradation; see `docs/sre/runbooks/api-gateway-high-error-rate.md`

---

## Test Coverage

| Test type   | File                                                     | What it validates                                |
| ----------- | -------------------------------------------------------- | ------------------------------------------------ |
| Integration | `tests/integration/test_hitl_gateway.py`                 | HITL approval and rejection mechanics            |
| Contract    | `tests/contract/pacts/frontend-api_gateway.json`         | Decision endpoint shape (interactions 7–9)       |
| Unit        | `tests/unit/agents/test_hitl_gateway.py`                 | Gateway timeout, state transitions               |
| E2E         | `tests/e2e/test_hitl_operator_ui.py` _(Wave 10)_         | Full operator journey from UI                    |
| Performance | `tests/performance/k6/hitl-decision-load.js` _(Wave 10)_ | Decision endpoint under concurrent operator load |
