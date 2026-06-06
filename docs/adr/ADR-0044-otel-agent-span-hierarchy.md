# ADR-0044: OTel Agent Span Hierarchy

| Field       | Value          |
| ----------- | -------------- |
| **Status**  | Accepted       |
| **Date**    | 2026-06-06     |
| **Authors** | Platform Team  |
| **Spec**    | OTEL-001 §2–§3 |
| **Issues**  | #27            |

---

## Context

The orchestrator (`src/agents/orchestrator/orchestrator.py`) and harness coordinator
(`src/agents/harness/coordinator.py`) had no OTel instrumentation. When an agent task
failed or exhibited unexpected latency, there was no way to identify which phase (perceive /
reason / act) was the bottleneck, or whether the harness planner or evaluator caused the
delay. All agent traffic appeared as undifferentiated HTTP spans in Jaeger.

## Decision

Introduce a mandatory span hierarchy under a canonical `agent.task` root span:

```
agent.task
  agent.perceive    ← PII masking + injection guard
  agent.reason      ← LLM call
    llm.inference   ← GenAI semantic conventions (see ADR-0045)
  agent.act         ← risk scoring + HITL routing
    tool.hitl_gateway ← HITL submission/decision (see ADR-0046)
harness.coordinator
  harness.planner   ← ProductSpec generation (full mode only)
  harness.evaluator ← per-iteration evaluation (with retry links)
```

All span names are defined as constants in `src/observability/span_hierarchy.py`. A single
module-level `tracer = trace.get_tracer("agentic-sdlc")` is imported by all instrumented
modules to keep the instrumentor name consistent.

### Mandatory attributes

See OTEL-001 §3 for the full attribute table. Key attributes per span:

- `agent.task` — `agent.id`, `agent.task_id`, `agent.harness_mode`
- `agent.perceive` — `perceive.pii_fields_masked`, `perceive.injection_guard_passed`
- `agent.reason` — `reason.model`, `reason.precedents_injected`
- `agent.act` — `act.action_type`, `act.risk_score`, `act.hitl_required`, `act.autonomous`
- `harness.evaluator` — `harness.stage`, `harness.iteration`, `harness.is_retry`, `harness.passed`

### Error propagation

`StatusCode.ERROR` is set on the parent span whenever a guardrail rejects input or a
phase raises an unhandled exception. This ensures the `errors-and-rejections` tail sampling
policy (ADR-0043) captures 100% of failed agent tasks.

## Consequences

**Positive:**

- Full phase-level visibility — bottlenecks can be attributed to perceive/reason/act.
- Evaluator retry chains are traceable: each `harness.evaluator` span records the iteration
  and `is_retry` flag.
- Compatible with the tail sampling policy: error spans propagate `StatusCode.ERROR` up to
  the root `agent.task` span.

**Negative / Trade-offs:**

- Small latency overhead per span (~1–2 µs for in-process SDK span creation).
- Developers must patch `src.agents.orchestrator.orchestrator.tracer` (not
  `src.observability.span_hierarchy.tracer`) in unit tests because of Python's `from ... import`
  binding semantics.

## Alternatives Considered

- **Auto-instrumentation only**: The OTel Python auto-instrumentation agent can instrument HTTP
  and DB calls but has no semantic understanding of the perceive/reason/act phases — manual
  instrumentation is required.
- **Single root span without child phases**: Loses the per-phase breakdown; not viable for
  production diagnosis.
