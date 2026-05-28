# Agent Performance Metrics — Specification

**ID:** SPEC-agent-performance  
**Version:** 1.0.0  
**Status:** Approved  
**Owner:** SRE Lead  
**ADR:** ADR-0004 (Observability Stack)

---

## 1. Purpose

Provide MTTD and MTTR visibility for agentic workflows, enabling SRE teams to measure how quickly the agent detects problems and restores resolution, and at what token cost.

---

## 2. Scope

Metrics defined here cover:

- **MTTD** (Mean Time To Detection): from problem trigger to first agent action start
- **MTTR** (Mean Time To Resolution): from first agent action start to verified resolution (evaluator pass or HITL approval)
- **Autonomous Resolution Rate**: fraction of tasks resolved without HITL escalation
- **Cost Per Resolution**: LLM tokens consumed per successfully resolved task

---

## 3. Metric Definitions

| Metric name                        | Type      | Labels        | Description                                              |
| ---------------------------------- | --------- | ------------- | -------------------------------------------------------- |
| `agent_mttd_seconds`               | Histogram | `action_type` | Time from problem detection to agent action start        |
| `agent_mttr_seconds`               | Histogram | `action_type` | Time from action start to verified resolution            |
| `agent_autonomous_resolution_rate` | Gauge     | `action_type` | Fraction [0,1] of tasks resolved without HITL escalation |
| `agent_cost_per_resolution_tokens` | Histogram | `action_type` | Total LLM tokens consumed per resolved task              |

### 3.1 MTTD Buckets

`(1, 5, 10, 30, 60, 120, 300, 600)` seconds — covers sub-minute to 10-minute detection windows.

### 3.2 MTTR Buckets

`(10, 30, 60, 120, 300, 600, 1800, 3600)` seconds — covers 10-second quick fixes to 1-hour resolutions.

### 3.3 Token Buckets

`(100, 500, 1000, 2000, 5000, 10000, 20000, 50000)` tokens.

---

## 4. Recording Rules

- MTTD is measured from the moment the harness coordinator receives a task to when the generator starts its first LLM call.
- MTTR is measured from the first generator LLM call to the moment an `EvaluatorScore.PASS` is returned or HITL approval is received.
- Autonomous resolution rate is updated after each sprint; value is 1.0 if no HITL escalation occurred, 0.0 otherwise. A rolling window is maintained at the metrics aggregation layer (Prometheus recording rules).
- Token cost is only recorded on successful resolution (pass or HITL approval), not on escalation-without-resolution.

---

## 5. Dashboard

Dashboard JSON at: `infrastructure/monitoring/grafana/dashboards/agent-performance.json`

Panels:

1. MTTD p50 / p99 over time (time series)
2. MTTR p50 / p99 over time (time series)
3. Autonomous Resolution Rate (gauge panel, target ≥ 0.80)
4. Cost Per Resolution — token p50 / p99 (time series)

---

## 6. SLO Targets

| Signal                     | Target          |
| -------------------------- | --------------- |
| MTTD p99                   | ≤ 60 s          |
| MTTR p99                   | ≤ 600 s         |
| Autonomous resolution rate | ≥ 80%           |
| Cost per resolution p99    | ≤ 10 000 tokens |
