# ADR-0025 — Language Selection for New Services

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead
**Reviewers:** Platform Team

---

## Context

The monorepo supports four runtimes: Python, Java, Go, and Node/Next.js. Without a clear decision rule, teams default to whichever language they know best, leading to inconsistent observability, guardrail coverage, and operational burden. A shared decision matrix reduces per-service debate and keeps the platform coherent.

---

## Decision

New services must be implemented in the language that best matches the primary workload type, not team preference alone.

### Decision Matrix

| Workload type | Recommended language | Rationale |
|---|---|---|
| LLM calls, HITL gateway, guardrails, AI agents | **Python** | Anthropic SDK, guardrails library, and all agent primitives are implemented in Python first |
| Complex domain logic, transactional workflows, DDD-heavy services | **Java (Spring Boot)** | Strong typing, mature transaction management, rich ecosystem for domain modelling |
| High-throughput event workers, sidecars, infrastructure glue | **Go** | Native concurrency model, low memory footprint, fast startup for Kafka consumers |
| Customer-facing UI, operator dashboards, HITL approval interface | **Node / Next.js** | SSR + React Query + OpenAPI client generation; aligned with frontend quickstart |
| Scheduled batch jobs, data pipelines | **Python** | APScheduler / Celery integration; guardrail and audit libraries available |

### Overrides

A team may deviate from the matrix if:
1. The deviation is justified in the PR referencing this ADR
2. The Tech Lead approves in the PR review
3. The service still satisfies the guardrail, observability, and HITL requirements in its chosen language (see `docs/quickstart/<language>-backend.md`)

---

## Consequences

- Reduces per-service language debate for common workload types
- Guardrail library coverage (PII filter, action limits, audit logger) is Python-native; other languages call the Python API gateway or implement equivalent logic per their quickstart guide
- New runtime additions (e.g., Rust) require a new ADR superseding this one

---

## Alternatives Considered

**Any language, team chooses freely** — rejected because it leads to fragmented guardrail coverage and inconsistent observability instrumentation.

**Python-only monorepo** — rejected because Java is strongly preferred for transactional domain services (ADR-0002) and Go has material advantages for high-throughput consumers.
