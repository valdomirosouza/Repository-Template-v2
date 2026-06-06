# Spec: OTel Agentic AI Observability

> **Spec ID:** OTEL-001
> **Status:** Approved
> **Version:** 1.0.0
> **Date:** 2026-06-05
> **Author:** Platform Team
> **ADRs:** ADR-0043, ADR-0044, ADR-0045, ADR-0046
> **Issues:** #26, #27, #28, #29, #30
> **Reference:** otel-agentic-ai-compliance-v2.md

---

## 1. Purpose

Define the authoritative OTel instrumentation contract for all agentic workloads. Every agent task
trace MUST conform to the span hierarchy, attribute conventions, and sampling policy defined here.

---

## 2. Required Span Hierarchy

```
Span: agent.task                [agent-level — root of every agent invocation]
  ├─ Span: agent.perceive       [orchestration — PII masking + injection guard]
  ├─ Span: agent.reason         [orchestration — LLM call]
  │     └─ Span: llm.inference  [execution — GenAI semantic conventions]
  ├─ Span: agent.act            [orchestration — HITL routing + execution]
  │     └─ Span: tool.hitl_gateway [execution — HITL submission/decision]
  └─ (harness mode = full | simplified)
        ├─ Span: harness.planner    [orchestration-level harness stage]
        ├─ Span: harness.coordinator [orchestration-level]
        └─ Span: harness.evaluator  [orchestration-level — with retry links]
```

---

## 3. Mandatory Span Attributes

### 3.1 agent.task

| Attribute            | Type   | Example                      |
| -------------------- | ------ | ---------------------------- |
| `agent.task_id`      | string | `req-abc-123`                |
| `agent.session_id`   | string | `sess-xyz-456`               |
| `agent.id`           | string | `summariser-v1`              |
| `agent.harness_mode` | string | `solo \| simplified \| full` |

### 3.2 agent.perceive

| Attribute                         | Type  | Example |
| --------------------------------- | ----- | ------- |
| `perceive.pii_fields_masked`      | int   | `3`     |
| `perceive.injection_guard_passed` | bool  | `true`  |
| `perceive.injection_risk_score`   | float | `0.12`  |

### 3.3 agent.reason

| Attribute                    | Type   | Example             |
| ---------------------------- | ------ | ------------------- |
| `reason.model`               | string | `claude-sonnet-4-6` |
| `reason.precedents_injected` | bool   | `false`             |

### 3.4 llm.inference (GenAI Semantic Conventions — OTel GenAI spec 2025)

| Attribute                       | Type   | Example             |
| ------------------------------- | ------ | ------------------- |
| `gen_ai.system`                 | string | `anthropic`         |
| `gen_ai.request.model`          | string | `claude-sonnet-4-6` |
| `gen_ai.request.max_tokens`     | int    | `4096`              |
| `gen_ai.request.temperature`    | float  | `1.0`               |
| `gen_ai.usage.input_tokens`     | int    | `512`               |
| `gen_ai.usage.output_tokens`    | int    | `128`               |
| `gen_ai.response.finish_reason` | string | `end_turn`          |

Optional (debug only, gated by `OTEL_LLM_CAPTURE_PROMPTS=true`, deleted by Collector in production):

| Event          | Attribute | Max length |
| -------------- | --------- | ---------- |
| `llm.prompt`   | `content` | 2000 chars |
| `llm.response` | `content` | 2000 chars |

### 3.5 agent.act

| Attribute           | Type   | Example      |
| ------------------- | ------ | ------------ |
| `act.action_type`   | string | `send-email` |
| `act.risk_score`    | float  | `0.72`       |
| `act.hitl_required` | bool   | `true`       |
| `act.autonomous`    | bool   | `false`      |

### 3.6 harness.\* spans

| Attribute           | Type   | Example                               |
| ------------------- | ------ | ------------------------------------- |
| `harness.stage`     | string | `planner \| coordinator \| evaluator` |
| `harness.iteration` | int    | `1`                                   |
| `harness.is_retry`  | bool   | `false`                               |
| `harness.passed`    | bool   | `true`                                |

### 3.7 hitl.decision (linked span)

| Attribute                    | Type   | Example                |
| ---------------------------- | ------ | ---------------------- |
| `hitl.decision`              | string | `approved \| rejected` |
| `hitl.decided_by`            | string | `operator@example.com` |
| `hitl.wait_duration_seconds` | float  | `247.5`                |
| `hitl.action_type`           | string | `send-email`           |
| `hitl.risk_score`            | float  | `0.72`                 |

### 3.8 Guardrail span events (on current active span)

| Event name                    | Attributes                         |
| ----------------------------- | ---------------------------------- |
| `guardrail.pii_detected`      | `pii_field_count`, `pii_max_level` |
| `guardrail.injection_blocked` | `rejection_reason`, `risk_score`   |

---

## 4. Collector PII Redaction (Defense-in-Depth)

Two-layer defense:

1. **Application layer** — `pii_filter.py` masks PII before any LLM call or log write
2. **Collector layer** — OTTL `transform/redact_pii` applies regex patterns to span attribute values

Collector redaction rules (all environments):

- `sk-ant-*` API keys in any attribute value → `sk-ant-***REDACTED***`
- `Bearer *` tokens → `Bearer ***REDACTED***`
- Email addresses → `***EMAIL_REDACTED***`
- Brazilian CPF (LGPD L1) → `***CPF_REDACTED***`
- API keys in span status messages → redacted

Production-only:

- `llm.prompt` span events deleted before export to Jaeger
- `llm.response` span events deleted before export to Jaeger

---

## 5. Tail Sampling Policy

Head-based sampling applies at the HTTP API layer (Jaeger `sampling-strategies.json`).
Tail-based sampling applies at the OTel Collector for agent spans.

| Policy                  | Condition                                                                  | Rate |
| ----------------------- | -------------------------------------------------------------------------- | ---- |
| `errors-and-rejections` | ERROR status OR `act.hitl_decision=rejected` OR `guardrail.violation=true` | 100% |
| `hitl-endpoints`        | `/v1/hitl/*` or `/v1/requests` HTTP routes                                 | 100% |
| `standard-agent-tasks`  | All other agent spans                                                      | 10%  |

`decision_wait: 10s` — Collector waits 10s for all spans in a trace before deciding.

---

## 6. Prometheus Exemplars

`llm_tokens_total` counter MUST carry a `request_id` label enabling Grafana Exemplar
pivot from Prometheus → Jaeger trace.

---

## 7. HITL Trace Linking

When a HITL request is submitted, the trace context (`trace_id`, `span_id`) is stored
alongside the HITL record. When a human decision arrives, a linked `hitl.decision` span
is created with `SpanContext.links` referencing the original `agent.task` trace.

---

## 8. Retry Span Links

When the Evaluator triggers a Generator/Coordinator retry, the retry span MUST carry
a `SpanLink` referencing the failed iteration span context. This enables full
reconstruction of the correction chain in Jaeger.
