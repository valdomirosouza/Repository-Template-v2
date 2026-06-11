# Developer Quickstart Guides

This directory contains role-specific onboarding guides for every developer persona
working in this monorepo. Start with the guide that matches your stack.

---

## Which guide is mine?

| I am building...                       | Guide                                  |
| -------------------------------------- | -------------------------------------- |
| A Python API or AI agent service       | [python-backend.md](python-backend.md) |
| A Java/Spring Boot domain service      | [java-backend.md](java-backend.md)     |
| A Go high-throughput worker or sidecar | [go-backend.md](go-backend.md)         |
| A React / Next.js frontend application | [frontend.md](frontend.md)             |
| A scheduled job or batch processor     | [jobs-worker.md](jobs-worker.md)       |

After reading your language guide, read these in order:

| Topic                                           | Guide                                              |
| ----------------------------------------------- | -------------------------------------------------- |
| Generating code from OpenAPI / AsyncAPI / proto | [contract-driven-dev.md](contract-driven-dev.md)   |
| Registering a new service in the monorepo       | [add-new-service.md](add-new-service.md)           |
| Deploying to production (canary, CAB, rollback) | [deploy-to-production.md](deploy-to-production.md) |

---

## What is shared across all languages

Before reading your language guide, understand the shared layer:

| Asset                  | Location                                                                     | What it is                                              |
| ---------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------- |
| Service catalog        | [`services.yaml`](../../services.yaml)                                       | All services, their language, port, and topic contracts |
| REST contract          | [`docs/api/openapi/v1/openapi.yaml`](../api/openapi/v1/openapi.yaml)         | OpenAPI 3.1 — the canonical REST API                    |
| Event contract         | [`docs/api/asyncapi/v1/asyncapi.yaml`](../api/asyncapi/v1/asyncapi.yaml)     | AsyncAPI 2.6 — all Kafka topics and event schemas       |
| Avro schemas           | `infrastructure/message-broker/schema-registry/avro/`                        | Event payload schemas (language-neutral)                |
| gRPC contracts         | [`docs/api/grpc/proto/ai_service.proto`](../api/grpc/proto/ai_service.proto) | Protobuf definitions for inter-service calls            |
| Shared config          | [`.env.example`](../../.env.example)                                         | Infrastructure variables (DB, Redis, Kafka, OTel)       |
| Architecture decisions | [`docs/adr/`](../adr/README.md)                                              | Binding decisions — read before writing code            |
| AI governance          | [`specs/ai/`](../../specs/ai/README.md)                                      | HITL/HOTL model, guardrails, agent design               |

> **Rule:** Never duplicate shared contracts in your service. Consume the OpenAPI/AsyncAPI/proto
> files as the source of truth. Generate clients from them — do not write them by hand.

---

## Governance that applies to every language

These rules are language-independent. Every service must comply.

| Rule                                            | Where defined                  | What you must do                                                         |
| ----------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------ |
| All agent actions route through HITL            | `CLAUDE.md §3.3`               | Call the HITL REST API before executing high-risk actions                |
| PII must be masked before logging and LLM calls | `specs/ai/guardrails.md`       | Use the PII masking service or implement the equivalent in your language |
| All agent actions must be audit-logged          | `specs/ai/guardrails.md`       | POST to the audit-logger endpoint or use its gRPC stub                   |
| Structured JSON logs                            | `specs/system/architecture.md` | Use OTel-compatible JSON logging with `trace_id` and `span_id`           |
| Golden Signals metrics                          | `skills/sre/golden-signals.md` | Instrument `requests_total`, `request_duration`, `errors_total`          |
| Unit test coverage ≥ 80%                        | `CLAUDE.md §3.5`               | Enforced in CI — PRs fail below this threshold                           |

> **Driving a feature end-to-end?** Once your spec is approved, **[Delivering a Spec with `/deliver`](delivering-a-spec.md)** explains every option (mode · tier · language) for taking it through all 15 phases — language-agnostic.

---

## Environment setup (all languages)

```bash
# 1. Clone the repository (or use as GitHub template)
git clone https://github.com/your-org/your-project.git && cd your-project

# 2. Start the shared infrastructure stack
docker compose up -d
# Brings up: PostgreSQL, Redis, Kafka, OTel Collector, Jaeger, Grafana, Prometheus

# 3. Copy and fill shared environment variables
cp .env.example .env
# Edit DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY, SECRET_KEY

# 4. Follow your language-specific guide for the remaining steps
```

---

## ADRs you must read before writing code

| ADR                                                              | Decision                                              |
| ---------------------------------------------------------------- | ----------------------------------------------------- |
| [ADR-0001](../adr/ADR-0001-monorepo-structure-and-governance.md) | Monorepo governance rules                             |
| [ADR-0003](../adr/ADR-0003-async-api-strategy.md)                | Async-first — when to use Kafka vs REST vs gRPC       |
| [ADR-0011](../adr/ADR-0011-hitl-hotl-model.md)                   | HITL/HOTL human oversight model                       |
| [ADR-0012](../adr/ADR-0012-pii-masking-strategy.md)              | PII masking before LLM ingestion and logging          |
| [ADR-0015](../adr/ADR-0015-feature-flag-strategy.md)             | Feature flags via OpenFeature + flagd                 |
| [ADR-0025](../adr/ADR-0025-language-selection.md)                | Language selection — when to use Python vs Java vs Go |
