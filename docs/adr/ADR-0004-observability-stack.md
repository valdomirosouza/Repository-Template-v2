# ADR-0004 — Observability Stack

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead, SRE Lead

---

## Context

The system includes multiple components (API Gateway, Agent Service, HITL Gateway, Audit Logger)
and must satisfy SLO targets defined in `docs/sre/slo/slo.yaml`. Operators need:

- Unified metrics, traces, and logs from all components without vendor lock-in
- Golden Signals (Traffic, Error Rate, Saturation, Latency) as the primary SLO signal
- Distributed tracing to correlate a single user request across async Kafka hops
- Structured logs that are PII-masked before export (ADR-0012)

---

## Decision

Adopt a **vendor-neutral OpenTelemetry SDK** with the following backend stack:

| Signal  | Collection             | Storage / Visualization               |
| ------- | ---------------------- | ------------------------------------- |
| Traces  | OTel SDK → OTLP/gRPC   | OTel Collector → Jaeger               |
| Metrics | OTel SDK → OTLP/gRPC   | OTel Collector → Prometheus → Grafana |
| Logs    | Structured JSON → OTLP | OTel Collector → log aggregator       |

Propagation: **W3C TraceContext** (`traceparent` header) across all service boundaries,
including Kafka message headers.

Implementation entry point: `src/observability/otel_setup.py`
Prometheus alert rules: `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`
Grafana dashboards: `infrastructure/monitoring/grafana/dashboards/`

---

## Consequences

### Positive

- OTel SDK decouples instrumentation from backend — swapping Jaeger for Tempo or
  Prometheus for VictoriaMetrics requires only collector config changes, not code changes.
- W3C TraceContext propagation through Kafka headers allows end-to-end trace correlation
  from API request to async agent action to audit record.
- Prometheus + Grafana are self-hosted, eliminating per-metric ingestion costs at scale.
- Golden Signals dashboards are version-controlled as JSON in `infrastructure/monitoring/`.

### Negative / Trade-offs

- Self-hosted Prometheus, Grafana, Jaeger add operational overhead vs. a managed SaaS.
- Long-term metric retention requires Thanos or Cortex (not yet adopted — see future ADR).
- OTel SDK adds ~5ms startup latency; acceptable given async-first design.

---

## Alternatives Considered

**Datadog**
Rejected: per-host + per-metric pricing becomes prohibitive at scale; vendor lock-in
for both instrumentation API and backend.

**Elastic Stack (ELK)**
Rejected: high memory footprint for Elasticsearch; licensing changes in 7.x+;
Kibana dashboard management is less ergonomic than Grafana for Golden Signals.

**AWS CloudWatch**
Rejected: cloud-vendor lock-in; metric cardinality limits conflict with per-agent
label dimensions required by guardrail metrics.
