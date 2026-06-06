# ADR-0046: HITL Trace Linking and Guardrail Span Events

| Field       | Value             |
| ----------- | ----------------- |
| **Status**  | Accepted          |
| **Date**    | 2026-06-06        |
| **Authors** | Platform Team     |
| **Spec**    | OTEL-001 §7, §3.8 |
| **Issues**  | #29               |

---

## Context

When a human made a HITL approval/rejection decision hours after the original agent request,
there was no way to correlate the decision event in Jaeger with the original `agent.task`
trace. The HITL decision was audited but the trace linkage was missing, making root-cause
analysis across the approval lifecycle impossible. Additionally, guardrail violations (PII
detected, injection blocked) were logged but left no signal on the active OTel trace.

## Decision

### HITL trace linking

1. **At submission** (`submit_for_approval()`): capture the active span context using
   `trace.get_current_span().get_span_context()` and store the hex-encoded `trace_id` and
   `span_id` on the `HITLRequest` dataclass (`otel_trace_id`, `otel_span_id`).

2. **At decision** (`record_decision()`): call `_emit_decision_span()` which creates a
   `tool.hitl_gateway` span with a `SpanContext.links` entry pointing at the original
   `agent.task` span. Attributes: `hitl.decision`, `hitl.decided_by`,
   `hitl.wait_duration_seconds`, `hitl.action_type`, `hitl.risk_score`.

The link is created using `TraceFlags.SAMPLED` so Jaeger renders it as a connected trace
even when the original and decision spans are in different traces (long wait times).

Malformed stored context (e.g., invalid hex) is silently ignored; the decision span is
emitted without a link rather than failing.

### Guardrail span events

**`pii_filter.py`** — `PIIFilter.mask_dict()` detects PII matches in the input and, if any
are found, calls `current_span.add_event("guardrail.pii_detected", {...})` with:

- `pii_field_count`: total match count
- `pii_max_level`: minimum integer level value of detected PII (lower = more sensitive)

**`prompt_injection_guard.py`** — `PromptInjectionGuard.validate()` emits
`"guardrail.injection_blocked"` span event with `rejection_reason` and `risk_score` when
the risk threshold is exceeded; also sets `span.set_status(StatusCode.ERROR, ...)` so the
tail sampling `errors-and-rejections` policy (ADR-0043) captures these traces at 100%.

Both guardrail modules check `span.is_recording()` before adding events to avoid overhead
when no active span exists (e.g., tests without OTel provider).

## Consequences

**Positive:**

- HITL decision traces are linked to the original `agent.task` trace in Jaeger — full
  audit timeline reconstruction is now possible.
- Guardrail violations are visible on the trace without parsing log lines.
- Injection-blocked traces are guaranteed to be sampled at 100% via the ERROR status.

**Negative / Trade-offs:**

- `otel_trace_id` / `otel_span_id` stored on `HITLRequest` add two fields to the dataclass
  and to any serialized form (Redis, DB). Existing serialized requests without these fields
  will have empty strings (safe — decision span emitted without link).
- PII detection in `mask_dict()` runs the detector twice (once to detect, once to mask).
  Performance impact is negligible for the call volume of the orchestrator, but should be
  reviewed if `mask_dict()` is called in a hot inner loop.

## Alternatives Considered

- **Store W3C `traceparent` header**: Equivalent approach; hexadecimal fields chosen for
  simpler reconstruction without an additional dependency.
- **Baggage propagation**: Would require injecting baggage at the HTTP API boundary and
  propagating it through Kafka; more complex for the HITL async lifecycle.
- **Structured log correlation only**: Insufficient — operators debugging a HITL issue need
  the full span timeline, not log grep.
