# System Architecture

**Status:** Approved | **Owner:** Tech Lead | **Last updated:** 2026-05-24

---

## Architecture Principles

1. **Async-first** — high-volume, latency-tolerant flows use events; sync only for health checks, HITL approvals, and direct user queries
2. **Privacy-by-design** — PII masking is structural, not optional; applied at three mandatory interception points
3. **Defence-in-depth** — multiple guardrail layers; no single point of trust failure
4. **Observable-by-default** — every component emits Golden Signals; no dark services
5. **HITL for consequential actions** _(AI Agents Module only)_ — when AI agents are enabled, no autonomous execution of real-world effects without human approval or explicit HOTL governance sign-off (ADR-0011)
6. **Spec-before-code** — no component is built without an approved spec

---

## Component Overview

```
                         ┌─────────────────┐
  User / Client ────────►│   API Gateway   │◄─── Health checks (sync)
                         │   (FastAPI)     │
                         └────────┬────────┘
                                  │ REST (sync)
                         ┌────────▼────────┐
                         │  Kafka Broker   │◄──► Schema Registry (Avro)
                         └────────┬────────┘
                                  │ Events (async)
                    ┌─────────────▼──────────────┐
                    │       Agent Service         │
                    │  Perception → Reason → Act  │
                    │  ┌─────────────────────┐   │
                    │  │  PII Filter         │   │
                    │  │  Injection Guard    │   │
                    │  │  Action Limits      │   │
                    │  └─────────────────────┘   │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │      HITL Gateway           │
                    │  (consequential actions)    │
                    └─────────────┬──────────────┘
                                  │ Approve/Reject
                    ┌─────────────▼──────────────┐
                    │      Audit Logger           │
                    │  (immutable, append-only)  │
                    └────────────────────────────┘
```

---

## Technology Stack

| Layer           | Technology                                    | ADR                |
| --------------- | --------------------------------------------- | ------------------ |
| REST API        | FastAPI (Python)                              | ADR-0002           |
| Async events    | Apache Kafka + AsyncAPI 2.6                   | ADR-0003, ADR-0005 |
| Agent framework | Custom Perception→Reason→Act loop             | ADR-0010           |
| LLM provider    | Configurable via `LLM_PROVIDER` env var       | ADR-0010           |
| Observability   | OpenTelemetry + Prometheus + Grafana + Jaeger | ADR-0004           |
| Secrets         | Vault / AWS Secrets Manager                   | ADR-0008           |
| Caching         | Redis (L2) + Vector DB (L3 semantic/RAG)      | ADR-0009           |
| Deployment      | Kubernetes + Helm (canary + blue-green)       | ADR-0006           |
| Service mesh    | Istio / Linkerd (TBD)                         | ADR-0007           |

---

## Data Flow

```
1. User submits request → API Gateway
2. API Gateway validates, rate-limits, publishes domain.created event
3. Event consumer routes to Agent Service
4. Agent Service:
   a. PII Filter masks user context (BEFORE LLM call)
   b. LLM call with masked context → proposed action
   c. Risk scorer evaluates action
   d. Score < threshold → HOTL (execute autonomously)
   e. Score ≥ threshold → HITL Gateway (request stored as waiting_for_human_approval)
5. Human decides via POST /v1/hitl/requests/{id}/decision → agent.action.approved|rejected
   → ApprovalConsumer executes the *stored* action through ToolExecutor (hitl_approved=True)
   and settles the request: completed | failed | rejected | expired (ADR-0086)
6. Audit Logger records all decisions (immutable)
7. User notified via webhook or polling
```

PII masking applied at steps 4a (pre-LLM), and also before any log write and
before any broker publish throughout the flow (ADR-0012).

---

## Runtime Wiring Invariants (ADR-0089)

Every capability this spec, CLAUDE.md §0.1 or an accepted ADR describes as part of the runtime
is constructed by the application lifespan (`src/api/rest/main.py`) and asserted by
`tests/integration/test_lifespan_wiring.py`, which boots the real lifespan offline (every
infrastructure client forced to its documented in-memory fallback). A capability documented
ahead of implementation must carry a "not wired" label with its tracking issue.

| Capability | Constructed by | Asserted by |
| --- | --- | --- |
| LLM client stack `Otel → Resilient → Timeout → Anthropic` (ADR-0044/0045/0075) | `src/agents/llm_factory.build_llm_client` | `test_llm_client_is_the_documented_wrapper_stack` |
| HTTP Golden Signals (`http_requests_total`, latency) | `GoldenSignalsMiddleware` | `test_http_golden_signals_middleware_is_installed` |
| Request consumer (Kafka or in-memory subscription) | lifespan → `RequestConsumer` | `test_submitted_request_is_processed_end_to_end_in_memory` |
| Approval consumer + HITL expiry sweep (ADR-0086) | lifespan → `ApprovalConsumer`, sweeper task | `test_approval_consumer_and_expiry_sweeper_are_running` |
| Agent concurrency semaphore (`max_concurrent_agents`) | lifespan; acquired per agent run | `test_semaphore_is_acquired_around_agent_runs` |
| Harness modes `simplified` / `full` (ADR-0014) | lifespan → `HarnessCoordinator` | `test_harness_coordinator_is_constructed_when_mode_is_not_solo` |
| `ai_agents_enabled=false` disables the extension at runtime | lifespan gate | `test_agents_disabled_starts_no_consumers` |

A new documented runtime capability adds a row here and an assertion there in the same PR.

---

## Integration Boundaries

| External system  | Protocol       | Data sent                        | PII handling                  |
| ---------------- | -------------- | -------------------------------- | ----------------------------- |
| LLM provider API | HTTPS/REST     | Masked context only              | Mandatory filter before call  |
| Kafka broker     | Kafka protocol | Events with masked fields        | Filter before publish         |
| Log aggregator   | OTel OTLP      | Structured JSON, masked          | Filter before write           |
| Vector DB (RAG)  | HTTP           | Embeddings of pseudonymised docs | Pseudonymised before indexing |

---

## Quality Attributes

| Attribute    | Target                                        | Mechanism                                  |
| ------------ | --------------------------------------------- | ------------------------------------------ |
| Availability | ≥ 99.9%                                       | HPA, PDB, multi-AZ, circuit breaker        |
| Latency p99  | ≤ 500ms (sync flows)                          | Async-first, Redis cache, OTel tracing     |
| Throughput   | Horizontal scale via HPA + Kafka partitioning |                                            |
| Security     | Zero Critical SAST/CVE findings               | CI gates, guardrails                       |
| Privacy      | Zero PII in external systems                  | Mandatory masking at 3 interception points |
| Auditability | 100% of agent actions logged                  | Immutable audit logger                     |
