# ADR-0043: OTel Collector OTTL PII Redaction + Tail Sampling

| Field       | Value          |
| ----------- | -------------- |
| **Status**  | Accepted       |
| **Date**    | 2026-06-06     |
| **Authors** | Platform Team  |
| **Spec**    | OTEL-001 §4–§5 |
| **Issues**  | #26            |

---

## Context

The OTel Collector already deleted specific PII attribute keys (`user.email`, `authorization`)
via `attributes/mask-pii`. However, PII could still leak as _values_ in arbitrary attributes —
for example, an Anthropic API key appearing in an error message attribute, or a CPF appearing
in a debug attribute emitted by new code. Additionally, all agent traces were exported at 100%,
making Jaeger storage unsustainable at production volume.

## Decision

### Layer 1: Value-based OTTL redaction

Add two `transform` processors before `attributes/mask-pii` in the traces and logs pipelines:

- `transform/redact_pii` — uses OTTL `replace_all_patterns()` to scan every attribute value
  with four regex patterns: Anthropic API keys (`sk-ant-*`), Bearer tokens, email addresses,
  and Brazilian CPF (LGPD L1). Applied to both traces and logs.
- `transform/redact_span_status` — uses OTTL `replace_pattern()` to redact API keys in span
  status messages.

`error_mode: ignore` is set on both processors so a malformed OTTL expression never blocks export.

### Layer 2: Tail-based sampling

Add a `tail_sampling` processor (OTel Collector contrib) at the end of the traces pipeline
before `batch`. Three policies in priority order:

| Policy                  | Condition                             | Rate |
| ----------------------- | ------------------------------------- | ---- |
| `errors-and-rejections` | ERROR status OR HITL rejected         | 100% |
| `hitl-full`             | `/v1/hitl/*` or `/v1/requests` routes | 100% |
| `standard-agent-tasks`  | Everything else                       | 10%  |

`decision_wait: 10s`, `num_traces: 50000`.

### Traces pipeline order

```
memory_limiter → transform/redact_pii → transform/redact_span_status →
attributes/mask-pii → resource → tail_sampling → batch
```

## Consequences

**Positive:**

- Defense-in-depth: value-level PII is redacted at the Collector even if the application layer
  misses it.
- 10% baseline sampling reduces Jaeger storage by ~90% while preserving 100% of errors and
  all HITL traces.
- `error_mode: ignore` protects export availability.

**Negative / Trade-offs:**

- `tail_sampling` requires the Collector to buffer up to `num_traces` traces for `decision_wait`
  seconds — increases Collector memory footprint (~50 k × avg spans × avg span size).
- Standard-agent-tasks at 10% means 90% of clean low-risk traces are not stored in Jaeger;
  increase sampling if deeper debugging is needed in staging.
- The OTel Collector image must be `otel/opentelemetry-collector-contrib` (not the slim core
  image) because `transform` and `tail_sampling` processors are contrib-only.

## Alternatives Considered

- **Head-based sampling only**: Cannot guarantee 100% of error traces are kept.
- **50% baseline sampling**: Higher storage cost without proportional observability gain.
- **No value-based redaction**: Application-layer masking is correct but one mis-instrumented
  span could leak PII to Jaeger — unacceptable for LGPD compliance.
