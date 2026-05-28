# CUJ-003 — Agent Autonomous Resolution

**CUJ ID:** CUJ-003
**Owner:** SRE Lead | **Last reviewed:** 2026-05-28

---

## User Role and Goal

**Role:** Authenticated end user submitting a request that the system resolves autonomously (HOTL path — no human approval required)
**Goal:** Submit a request and receive a processed result without any human-in-the-loop delay, within the latency SLO, with confidence that the agent operated within its approved autonomy boundaries and the action is fully audit-logged.

**Precondition:** The `autonomous-mode` feature flag is enabled at `LOW_RISK` or above (ADR-0015). With `NONE` (default), all actions require HITL — see CUJ-001 and CUJ-002 instead.

---

## SLO Targets

| Signal                         | Target                                                     | Window |
| ------------------------------ | ---------------------------------------------------------- | ------ |
| Autonomous resolution rate     | ≥ 80% of eligible actions resolved without HITL escalation | 30d    |
| End-to-end latency p95         | ≤ 5 000 ms from request submission to result available     | 30d    |
| Token cost p95                 | ≤ 5 000 tokens per resolution                              | 30d    |
| Self-reflection iterations p99 | ≤ 15 iterations per sprint                                 | 30d    |
| Agent action success rate      | ≥ 99.5% of autonomous actions complete without error       | 30d    |

---

## Step-by-Step Happy Path

```
1. User submits request via POST /v1/requests
   → 202 Accepted; request_id returned immediately

2. RequestConsumer picks up from store
   → AgentOrchestrator.run_cycle(context) invoked

3. Perception: PII masking
   → pii_filter.mask_dict(context) applied before LLM call
   → Masked context forwarded to LLM client

4. Reason: LLM inference
   → prompt_injection_guard checks input first (rejects if suspicious)
   → AnthropicLLMClient.generate() called
   → Proposed action returned

5. Act: Risk scoring and autonomy check
   → RiskScorer evaluates proposed action
   → risk_score < autonomy threshold → proceed autonomously
   → HITLGateway.submit() called; autonomy level allows auto-execute
   → action logged via audit_logger.py (ALWAYS, regardless of autonomy)

6. Action executed
   → SandboxExecutor runs action in isolated environment (ADR-0016)
   → Result captured and published as domain.result.completed event

7. (Harness mode = full): multi-sprint self-reflection
   → EvaluatorAgent scores the result
   → If score < threshold: retry with PatchProposal (max iterations: settings.max_sprint_iterations)
   → If max iterations reached: escalate to HITL (CUJ-002)
   → If passed: HarnessResult published

8. User polls GET /v1/requests/{id} or receives webhook
   → Status: completed
   → Result summary available (PII-masked)
```

---

## Grafana Dashboard

`infrastructure/monitoring/grafana/dashboards/agent-performance.json`

Key panels for this CUJ:

- Autonomous resolution rate (gauge — target ≥ 0.80)
- End-to-end p50/p99 latency (timeseries)
- Token cost per resolution p50/p95 (timeseries)
- Self-reflection iteration distribution (histogram)
- HITL escalation rate (timeseries — inverse of autonomous resolution)
- LLM call latency p99 (timeseries)

Additional: `infrastructure/monitoring/grafana/dashboards/finops-cost-allocation.json`

- Monthly token budget utilisation (gauge)
- Cost per resolution by action_type (table)

---

## Dependencies

| Dependency               | Type                    | Impact if unavailable                                      |
| ------------------------ | ----------------------- | ---------------------------------------------------------- |
| LLM provider (Anthropic) | Core                    | No inference; circuit breaker opens after 5 failures → 503 |
| Redis RequestStore       | Core                    | Cannot persist request state; users see 503                |
| PostgreSQL audit log     | Required                | Action blocked; no execution without audit record          |
| Kafka broker             | Async                   | Result event delayed; request stays in `processing` state  |
| SandboxExecutor          | Core (for code actions) | Code execution blocked; non-code actions unaffected        |
| Feature flags (flagd)    | Required                | Autonomy level falls back to NONE (safest default)         |

---

## Failure Scenarios

| Scenario                               | Trigger                          | Expected degradation                                                          | Recovery                                                       |
| -------------------------------------- | -------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------- |
| LLM provider timeout                   | Provider latency spike           | Retry with backoff (max 3); circuit breaker opens at 5 consecutive failures   | Monitor `llm_call_latency`; alert fires at p99 > 10 s          |
| Risk scorer escalates too many actions | Feedback bias at maximum         | Autonomous resolution rate drops; queue backlog grows                         | Review `agent_feedback_bias_applied`; see feedback-loop docs   |
| Self-reflection loop runaway           | Evaluator never passes           | Token cost p99 exceeds FinOps threshold; max iterations hit; escalate to HITL | `AgentCostPerResolutionHigh` alert; check evaluator thresholds |
| Sandbox OOM/timeout                    | Code action exceeds resource cap | Action fails; error result published; user notified                           | Review sandbox resource limits in ADR-0016                     |
| Feature flag returns NONE              | flagd unreachable                | All actions route to HITL; autonomous resolution = 0%                         | Restore flagd; safe-default by design (ADR-0015)               |
| Audit log write failure                | PostgreSQL unavailable           | Action execution **blocked** — system refuses to execute without audit record | P1 incident; restore PostgreSQL                                |

---

## Autonomy Boundary Enforcement

Every autonomous action must pass through `HITLGateway.submit()` even in HOTL mode. The gateway checks the autonomy level against the action's risk score before allowing execution. This invariant is tested in `tests/unit/agents/test_hitl_gateway.py`.

**FULL autonomy** is never the default. It requires ADR-0015 governance sign-off and is controlled exclusively by the `autonomous-mode` feature flag.

---

## SLO Degraded Path

When autonomous resolution rate drops below 80% (warning threshold):

1. Check feedback bias: `make agent-feedback-check`
2. If bias is at maximum (0.50): risk scorer is flagging too many actions — governance review required before adjusting
3. If LLM latency is high: check provider status; monitor circuit breaker
4. If HITL queue is growing: cross-reference with CUJ-002

---

## Test Coverage

| Test type   | File                                                   | What it validates                          |
| ----------- | ------------------------------------------------------ | ------------------------------------------ |
| Unit        | `tests/unit/agents/test_hitl_gateway.py`               | Autonomy level enforcement, risk threshold |
| Unit        | `tests/unit/agents/test_risk_scorer.py`                | Risk scoring logic                         |
| Integration | `tests/integration/test_request_pipeline.py`           | Full HOTL pipeline round-trip              |
| Security    | `tests/security/test_prompt_injection.py`              | Injection guard blocks before LLM          |
| Chaos       | `tests/chaos/experiments/llm-api-timeout.yaml`         | Circuit breaker opens on LLM failure       |
| Chaos       | `tests/chaos/experiments/agent-context-overflow.yaml`  | Context reset triggers correctly           |
| Performance | `tests/performance/k6/request-api-load.js` _(Wave 10)_ | Latency under load                         |
| E2E         | `tests/e2e/test_request_lifecycle.py` _(Wave 10)_      | Full autonomous resolution journey         |
