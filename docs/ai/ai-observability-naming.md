# AI Observability Naming Standard

> **Owner:** SRE Lead + AI Governance Lead | **Status:** Living standard
> The canonical reference for agent/LLM **span** and **metric** names. These names already exist in
> `specs/observability/otel-agentic-observability.md` (OTEL-001) and the Prometheus rules; this page
> consolidates them into one authoritative list so dashboards, alerts, and new instrumentation stay
> consistent. New AI instrumentation MUST reuse these names — do not invent parallel ones.

---

## Span hierarchy (OTel — `specs/observability/otel-agentic-observability.md`)

```
agent.task                  [root]
├─ agent.perceive           PII masking + injection guard
├─ agent.reason             LLM call
│  └─ llm.inference         GenAI semantic conventions (OTel 2025)
├─ agent.act                HITL routing + execution
│  └─ tool.hitl_gateway     HITL submission/decision
└─ harness.{planner|coordinator|evaluator}   (full/simplified modes)
```

### Span attributes

| Span             | Key attributes                                                                                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent.task`     | `agent.task_id`, `agent.session_id`, `agent.id`, `agent.harness_mode`                                                                                                                          |
| `agent.perceive` | `perceive.pii_fields_masked`, `perceive.injection_guard_passed`, `perceive.injection_risk_score`                                                                                               |
| `llm.inference`  | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.request.max_tokens`, `gen_ai.request.temperature`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reason` |
| `agent.act`      | `act.action_type`, `act.risk_score`, `act.hitl_required`, `act.autonomous`                                                                                                                     |
| `harness.*`      | `harness.stage`, `harness.iteration`, `harness.is_retry`, `harness.passed`                                                                                                                     |

Use the OTel **GenAI** convention (`gen_ai.*`) for all model-call attributes — never bespoke keys.

## Metrics (Prometheus — `infrastructure/monitoring/prometheus/rules/agent-alerts.yaml`)

| Metric                                           | Type      | Captures                               |
| ------------------------------------------------ | --------- | -------------------------------------- |
| `llm_call_duration_seconds`                      | histogram | model-call latency                     |
| `llm_tokens_total`                               | counter   | token usage                            |
| `llm_tokens_budget_total`                        | gauge     | 30-day token budget baseline (FinOps)  |
| `agent_cost_per_resolution_tokens`               | histogram | token cost per autonomous resolution   |
| `agent_mttd_seconds`                             | histogram | time-to-detect                         |
| `agent_mttr_seconds`                             | histogram | time-to-resolve                        |
| `agent_autonomous_resolution_rate`               | gauge     | share resolved without HITL escalation |
| `agent_semaphore_waiting`                        | gauge     | agent-concurrency backpressure         |
| `hitl_active_requests`                           | gauge     | HITL queue depth                       |
| `hitl_approvals_total` / `hitl_rejections_total` | counter   | HITL decision outcomes                 |
| `hitl_wait_seconds`                              | histogram | time to human decision                 |
| `agent_feedback_rejection_rate`                  | gauge     | feedback-loop rejection rate           |
| `agent_feedback_bias_applied`                    | gauge     | feedback bias magnitude                |
| `agent_behavioral_anomaly_total`                 | counter   | behavioural drift / anomaly            |
| `agent_policy_decision_total`                    | counter   | policy allow/block decisions           |
| `agent_groundedness_score`                       | gauge     | groundedness SLI 0.0–1.0 (ADR-0080)    |
| `agent_hallucination_flagged_total`              | counter   | unsupported (hallucinated) claim flags |
| `dlq_messages_total`                             | counter   | dead-letter accumulation               |

## Recommended AI dashboard signals (map to the metrics above)

Prompt version · model version (`gen_ai.request.model`) · agent action type (`act.action_type`) ·
tool-call count · token usage (`llm_tokens_total`) · cost/request (`agent_cost_per_resolution_tokens`) ·
HITL escalation rate · HITL rejection rate (`hitl_rejections_total`) · guardrail block rate
(`agent_policy_decision_total`) · agent retry count (`harness.iteration`) · time-to-human-decision
(`hitl_wait_seconds`) · time-to-autonomous-resolution (`agent_mttr_seconds`).

## PII redaction in telemetry

- Application layer masks via `pii_filter` before any LLM call (CLAUDE.md §3.1).
- Collector layer redacts residual patterns (OTTL transform) and, in production, drops `llm.prompt` /
  `llm.response` span events before export (`specs/observability/otel-agentic-observability.md`).
- Tail sampling keeps 100% of errors, HITL rejections, and guardrail violations.

## Gaps (target signals not yet emitted)

- **Groundedness / hallucination** is now **implemented** (ADR-0080):
  `agent_groundedness_score` (gauge, 0.0–1.0) + `agent_hallucination_flagged_total` (counter),
  recorded via `record_groundedness(...)` in `src/observability/metrics.py` and gated by
  `tests/model_contract/test_groundedness.py`.
- **Retrieval precision / grounding coverage** (`agent_retrieval_grounding_ratio`) and **prompt
  version** as a first-class `prompt_version` label are not yet instrumented. Add under those names
  when implemented.

---

## Related

- `specs/observability/otel-agentic-observability.md` (OTEL-001) — authoritative span/attr conventions
- `skills/observability/otel-instrumentation.md` · `specs/observability/agent-performance.md`
- `infrastructure/monitoring/prometheus/rules/agent-alerts.yaml`
- `docs/ai/eval-scorecard.md` · `specs/sre/finops.md`
