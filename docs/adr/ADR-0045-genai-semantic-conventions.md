# ADR-0045: GenAI Semantic Conventions for LLM Instrumentation

| Field       | Value             |
| ----------- | ----------------- |
| **Status**  | Accepted          |
| **Date**    | 2026-06-06        |
| **Authors** | Platform Team     |
| **Spec**    | OTEL-001 §3.4, §6 |
| **Issues**  | #28               |

---

## Context

`AnthropicLLMClient.complete()` called the Anthropic SDK and returned only the response text
string, discarding token counts (`usage.input_tokens`, `usage.output_tokens`, `stop_reason`,
`model`) that were available in the Anthropic response object. There was no `llm.inference`
span and no GenAI semantic convention attributes in any trace. Token metrics were recorded
via `record_llm_call()` but without a `request_id` dimension preventing Grafana → Jaeger
exemplar pivot.

## Decision

### `AnthropicLLMClient`

Add `complete_with_metadata() -> tuple[str, LLMCallMetadata]` method that returns the
response text alongside a `LLMCallMetadata` dataclass containing `input_tokens`,
`output_tokens`, `finish_reason`, and `model`. `complete()` delegates to this method and
discards the metadata (preserving the `LLMClient` protocol signature).

### `OtelLLMClientWrapper`

A new wrapper class in `src/agents/llm_client_otel.py` that wraps any `LLMClient` and:

1. Creates a child `llm.inference` span under the active span.
2. Sets GenAI semantic convention attributes:
   `gen_ai.system`, `gen_ai.request.model`, `gen_ai.request.max_tokens`,
   `gen_ai.request.temperature`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
   `gen_ai.response.finish_reason`.
3. Optionally attaches `llm.prompt` / `llm.response` span events gated by
   `settings.otel_capture_prompts` (default `False`). These events are stripped by the
   Collector `transform/redact_pii` processor before Jaeger export in production (ADR-0043).
4. Calls `record_llm_call()` with `request_id=trace_id` for Prometheus exemplar linking.

### `llm_tokens_total` counter label

Add `request_id` as a fourth label dimension so Grafana Exemplar queries can pivot from
a high-cardinality token spike to the specific Jaeger trace.

### GenAI semantic convention version

Following the OpenTelemetry GenAI spec (experimental, 2025 draft). Attribute names will be
stable-updated when the spec reaches GA.

## Consequences

**Positive:**

- Token usage is no longer silently discarded — every LLM call is observable.
- Grafana Exemplars enable direct pivot from `llm_tokens_total` to the Jaeger trace for
  the offending request.
- `otel_capture_prompts=False` default ensures prompt content never reaches Jaeger in
  production even if a developer accidentally enables it — the Collector strips the events.

**Negative / Trade-offs:**

- ~~`request_id` label on `llm_tokens_total` increases Prometheus cardinality.~~ **Resolved
  (W1-4, 2026-06-12):** the `request_id` label was removed — it was unbounded (one time series
  per request, OOM risk). `llm_tokens_total` is now `{service, model, token_type}`; per-request
  token cost lives on the OTel `llm.inference` span (`gen_ai.usage.*`), the correct drill-down.
- `OtelLLMClientWrapper` must be explicitly wired at the injection point (app startup).
  If not wired, `AnthropicLLMClient` calls are untraced (no silent breakage).

## Alternatives Considered

- **Return `LLMResponse` from `LLMClient.complete()`**: Breaks every caller in a large
  refactor. Deferred to a future major version.
- **Store metadata as instance variable**: Thread-unsafe under concurrent callers; rejected.
- **Auto-instrument Anthropic SDK**: The OTel Python `anthropic` instrumentation package
  exists but was not yet stable at the time of this decision; manual wrapping preferred.
