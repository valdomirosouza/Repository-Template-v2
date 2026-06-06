# Skill — OpenTelemetry Instrumentation

**Owner:** SRE Lead | **Reviewer:** Tech Lead | **Status:** Active | **Last updated:** 2026-06-06

Activate this skill for any work involving metrics, traces, logs, or OTel SDK usage.

Spec: specs/system/architecture.md, specs/observability/otel-agentic-observability.md (OTEL-001)
ADR: ADR-0004 (Observability Stack), ADR-0043–ADR-0046 (Agentic OTel)

---

## Setup

`setup_telemetry()` must be called once at application startup (`src/observability/otel_setup.py`).
It initialises traces (→ Jaeger), metrics (→ Prometheus), and W3C TraceContext propagation.

```python
from src.observability.otel_setup import setup_telemetry
setup_telemetry()  # call once in lifespan or __main__
```

---

## Adding Spans (Traces)

```python
from opentelemetry import trace

tracer = trace.get_tracer("my-component")

with tracer.start_as_current_span("action.name") as span:
    span.set_attribute("agent.id", agent_id)
    span.set_attribute("action.type", action_type)
    span.set_attribute("risk.score", risk_score)
    # ... do work
```

Required attributes for agent spans:

| Attribute           | Type   | Example               |
| ------------------- | ------ | --------------------- |
| `agent.id`          | string | `"summariser-v1"`     |
| `action.type`       | string | `"send_notification"` |
| `risk.score`        | float  | `0.75`                |
| `hitl.required`     | bool   | `true`                |
| `guardrail.outcome` | string | `"pass"` / `"reject"` |

---

## Agentic Span Hierarchy (OTEL-001, ADR-0044)

All agent tasks MUST use the canonical span constants from `src/observability/span_hierarchy.py`.
Never hardcode span name strings inline.

```python
from src.observability.span_hierarchy import (
    SPAN_AGENT_TASK, SPAN_AGENT_PERCEIVE, SPAN_AGENT_REASON, SPAN_AGENT_ACT,
    SPAN_LLM_INFERENCE, SPAN_TOOL_HITL_GATEWAY,
    SPAN_HARNESS_COORDINATOR, SPAN_HARNESS_PLANNER, SPAN_HARNESS_EVALUATOR,
    tracer,
)

with tracer.start_as_current_span(SPAN_AGENT_TASK) as span:
    span.set_attributes({"agent.id": agent_id, "agent.harness_mode": "solo"})
    # perceive / reason / act as child spans
```

**Test patching rule:** when patching `tracer` in unit tests, patch at the import site of the
instrumented module, NOT at `src.observability.span_hierarchy.tracer`:

```python
# CORRECT — patches the local binding in orchestrator.py
with patch("src.agents.orchestrator.orchestrator.tracer", test_tracer):
    ...

# WRONG — does not affect already-imported references
with patch("src.observability.span_hierarchy.tracer", test_tracer):
    ...
```

---

## LLM Inference Spans (OTEL-001 §3.4, ADR-0045)

Wrap production `AnthropicLLMClient` with `OtelLLMClientWrapper` at the injection point:

```python
from src.agents.llm_client_otel import OtelLLMClientWrapper
from src.shared.llm_client import AnthropicLLMClient

llm = OtelLLMClientWrapper(AnthropicLLMClient())
```

The wrapper emits an `llm.inference` child span with GenAI semantic convention attributes
(`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`, `gen_ai.response.finish_reason`)
and records `llm_tokens_total` with `request_id` for Grafana Exemplar → Jaeger pivot.

`OTEL_LLM_CAPTURE_PROMPTS=false` must remain `false` in production. The Collector strips
`llm.prompt`/`llm.response` span events in production even if the flag is enabled.

---

## HITL Trace Linking (OTEL-001 §7, ADR-0046)

`HITLGateway.submit_for_approval()` automatically captures the active span context.
`record_decision()` emits a linked `tool.hitl_gateway` span — no additional code required.

To ensure the link is populated, the HITL submission must occur within an active `agent.act`
or `agent.task` span. If called outside any span, the decision span is emitted without a link.

---

## Guardrail Span Events (OTEL-001 §3.8, ADR-0046)

`pii_filter.mask_dict()` and `prompt_injection_guard.validate()` automatically add span events
(`guardrail.pii_detected`, `guardrail.injection_blocked`) to the active span. No caller changes
are needed. Injection blocks also set `StatusCode.ERROR` on the span.

---

## Adding Metrics

Use the pre-defined metrics from `src/observability/metrics.py`. Do **not** create ad-hoc
Prometheus metrics — add to that module so the Golden Signals dashboard stays in sync.

```python
from src.observability.metrics import record_agent_action, record_request

# After a request completes:
record_request(service="api-gateway", method="POST", path="/v1/requests",
               status_code=202, duration_seconds=0.045)

# After an agent action completes:
record_agent_action(agent_id="summariser-v1", action_type="summarise",
                    result="success", duration_seconds=1.2)
```

**New metric checklist:**

- [ ] Counter: use `_total` suffix
- [ ] Histogram: define buckets aligned with the SLO threshold (p99 ≤ 500ms → include 0.5 bucket)
- [ ] Labels: keep cardinality bounded — never use user IDs or free-text as labels
- [ ] Add to `golden-signals.yaml` Prometheus rules if alertable
- [ ] Add to Grafana dashboard JSON if visualised

---

## Structured Logging

All log calls go through `src/observability/logger.py`. Never use `print()` or stdlib
`logging.info()` directly in application code.

```python
from src.observability.logger import get_logger

logger = get_logger("my-component")

logger.info("Action completed", agent_id=agent_id, action_type=action_type, duration_ms=45)
logger.warning("Rate limit approaching", agent_id=agent_id, remaining=5)
logger.error("Unexpected failure", error=str(exc), agent_id=agent_id)

# Audit events (identifiers NOT masked — required for legal traceability):
logger.audit("hitl_decision_recorded", request_id=request_id, decision="APPROVED")
```

**PII rule:** all context kwargs passed to `info()`, `warning()`, `error()` are masked
automatically by `pii_filter.mask_dict()` before emission. The `audit()` method bypasses
masking — use it only for non-PII identifiers (UUIDs, event types, outcomes).

---

## Kafka Trace Propagation

Inject the W3C `traceparent` header into Kafka message headers before produce:

```python
from opentelemetry.propagate import inject

headers: dict[str, str] = {}
inject(headers)  # populates "traceparent" and "tracestate"
await producer.send(topic, value=payload, headers=list(headers.items()))
```

Extract on the consumer side:

```python
from opentelemetry.propagate import extract

carrier = {k: v.decode() for k, v in record.headers}
ctx = extract(carrier)
with tracer.start_as_current_span("consume.event", context=ctx):
    ...
```

---

## Dashboards

| Dashboard      | File                                                               |
| -------------- | ------------------------------------------------------------------ |
| Golden Signals | `infrastructure/monitoring/grafana/dashboards/golden-signals.json` |
| SRE / SLO      | `infrastructure/monitoring/grafana/dashboards/sre-overview.json`   |
| Alert rules    | `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`   |
| OTel Collector | `infrastructure/monitoring/opentelemetry/otel-collector.yaml`      |
