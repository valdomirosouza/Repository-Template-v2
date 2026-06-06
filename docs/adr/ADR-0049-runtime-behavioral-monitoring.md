# ADR-0049: Runtime Behavioral Monitoring

**Status:** Accepted
**Date:** 2026-06-06
**Deciders:** Security Lead, AI Governance Lead
**Refs:** Issue #34, secure-by-design-agentic-ai-compliance-v2.md §Pillar 3 (BM1, BM2, BM3)

---

## Context

The monitoring stack (Prometheus + Jaeger) detects metric anomalies — latency, error rate,
token count — but not semantic behavioral drift. Three gaps exist:

- **BM1** — No semantic drift detector: if an agent that normally proposes `read_file` for
  a `summarise` task suddenly proposes `execute_code`, no alert fires. This is exactly the
  pattern expected from a prompt injection attack or model drift event.
- **BM2** — The HITL gateway enforces a static risk_score threshold. There is no adaptive
  policy layer that can express rules like "code execution is never permitted for
  summarization tasks, regardless of risk_score."
- **BM3** — No behavioral baseline: without tracking historical action proposal frequencies,
  BM1 drift detection is impossible.

---

## Decision

### BM1 + BM3 — BehavioralMonitor (`src/agents/behavioral_monitor.py`)

- `BehavioralMonitor.record_proposal(task_type, proposed_action)` — builds a per-task-type
  frequency distribution of historical action proposals. Requires `_MIN_OBSERVATIONS = 20`
  before activating (prevents false positives on cold start).
- `BehavioralMonitor.is_anomalous(task_type, proposed_action, allowed_action_types=None)` —
  returns `True` if the proposed action's historical frequency is below
  `_ANOMALY_FREQUENCY_THRESHOLD = 1%` AND the action is not in the spec's allowed list.
  On anomaly: sets OTel span attribute `behavioral.drift_detected=true` and increments
  `agent_behavioral_anomaly_total{task_type, action_type}` Prometheus counter.
- Backend: in-memory `defaultdict[str, ActionFrequency]`. Production deployments should
  replace with a Redis sorted-set backend for persistence across restarts.

### BM2 — RuntimePolicyGateway (`src/agents/runtime_policy_gateway.py`)

- Evaluates agent actions against a declarative YAML policy set loaded from
  `infrastructure/agent-policies/policies.yaml`.
- Policies are evaluated in order; first match wins; default is ALLOW.
- Decision types: `ALLOW | REQUIRE_HITL | BLOCK`. BLOCK raises `RuntimePolicyError`.
- `evaluate_or_raise()` is the blocking gate; `evaluate()` returns the decision for callers
  that handle it differently (e.g., forcing HITL routing).
- `reload(path)` enables hot-reload without restarting the process.
- Four starter policies ship in `policies.yaml`:
  - `no-code-execution-on-summarize` (BLOCK)
  - `external-write-always-hitl` (REQUIRE_HITL)
  - `pii-write-l2-always-hitl` (REQUIRE_HITL)
  - `execute-code-always-hitl` (REQUIRE_HITL)

### Prometheus Alerts

Two new alert rules in `agent-alerts.yaml`:

- `AgentBehavioralDrift` — fires immediately on any drift detection (severity: critical)
- `RuntimePolicyBlocked` — fires when BLOCK decisions exceed 0.1/s for 1 minute (severity: warning)

---

## Alternatives Considered

- **Redis-backed frequency store** — deferred; in-memory is sufficient for the baseline use
  case and avoids a Redis dependency in the hot path. Redis backend is a straightforward
  extension when persistence across restarts is required.
- **LLM-based semantic similarity check** — too expensive and introduces latency in the
  act phase. Frequency-based detection is deterministic and zero-latency.
- **OPA (Open Policy Agent)** — considered for policy evaluation but adds an external
  service dependency. YAML + Python evaluation is sufficient for the current policy
  complexity and avoids network calls in the critical path.

---

## Consequences

- **Security +**: Closes BM1/BM2/BM3. The combination of behavioral baseline + adaptive
  policies provides two independent behavioral safeguards at the act layer.
- **Prometheus**: Two new metrics (`agent_behavioral_anomaly_total`, `agent_policy_decision_total`)
  and two alert rules. Existing dashboards require manual update to include these panels.
- **Cold start**: BehavioralMonitor suppresses anomaly detection until 20 observations are
  collected per task_type. This is intentional — false positives on cold start would
  trigger excessive HITL escalations.
- **Policy ordering**: Policy authors must be aware that first-match-wins means more
  specific policies must appear before broader ones.
