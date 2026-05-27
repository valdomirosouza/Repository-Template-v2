# Spec: Agent Supervision Dashboard

**ID:** SPEC-agent-supervision
**Status:** Accepted
**Version:** 1.0.0
**Date:** 2026-05-26
**Authors:** Tech Lead, SRE Lead
**GitHub Issue:** required before merge

---

## 1. Purpose

Provide a real-time Grafana dashboard for human supervisors to monitor the state of
all active agents, the HITL approval queue, recent action outcomes, and FinOps cost
metrics. This dashboard is the primary human supervision interface for the agentic
system — it must load in under 2 seconds and refresh every 30 seconds.

---

## 2. Panels

| #   | Panel                              | Type        | Primary metric                                  |
| --- | ---------------------------------- | ----------- | ----------------------------------------------- |
| 1   | Active HITL Queue                  | Stat        | `hitl_active_requests`                          |
| 2   | HITL Queue — Pending by Agent      | Table       | `hitl_active_requests{agent_id}`                |
| 3   | HITL Approval vs Rejection Rate    | Time series | `hitl_approvals_total`, `hitl_rejections_total` |
| 4   | HITL Wait Time Distribution        | Histogram   | `hitl_wait_seconds_bucket`                      |
| 5   | Agent Actions — Success vs Failure | Time series | `agent_actions_total{result}`                   |
| 6   | Agent Action Latency (p50 / p99)   | Time series | `agent_action_duration_seconds`                 |
| 7   | LLM Token Usage (FinOps)           | Time series | `llm_tokens_total`                              |
| 8   | LLM Token Budget Remaining         | Gauge       | `llm_tokens_budget_total - llm_tokens_total`    |
| 9   | Jaeger Trace Link                  | Text        | Link to `agent_id` trace                        |
| 10  | Autonomous Resolution Rate         | Stat        | `hitl_approvals_total / agent_actions_total`    |

---

## 3. Data sources

- **Prometheus** (primary): all quantitative panels
- **Jaeger** (panel 9): deep-link to latest trace for a selected agent_id

---

## 4. Refresh and time range defaults

- Refresh: 30 s
- Default time range: last 1 hour
- Alert threshold: `hitl_active_requests > 50` → visual alert on panel 1

---

## 5. Acceptance criteria

- [ ] Dashboard loads without errors in Grafana 10+
- [ ] All panels reference valid Prometheus metric names from `src/observability/metrics.py`
- [ ] Panel 9 Jaeger link is parameterised by `agent_id` template variable
- [ ] Dashboard UID is `agent-supervision-v1`
