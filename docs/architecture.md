# System Architecture

**Owner:** Tech Lead | **Last updated:** 2026-05-28
**ADR references:** ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0010\*, ADR-0011\*

> **AI Agents Module is opt-in.** The _Agent Runtime_ subgraph (Orchestrator, Harness,
> Guardrails, HITL Gateway, LLM) is only present when the AI Agents Module is enabled.
> Projects that do not use AI agents will only have the API Layer, Infra, and Observability
> subgraphs. See [`docs/optional-extensions/ai-agents/README.md`](optional-extensions/ai-agents/README.md).
>
> ADRs marked \* are binding only when the AI Agents Module is active.

---

## System Topology

```mermaid
graph TD
    Client([Client / Browser])

    subgraph API Layer
        API[FastAPI :8000\n/v1/requests\n/v1/hitl/:id/decide\n/health  /ready  /metrics]
    end

    subgraph Infra
        Redis[(Redis :6379\nHITL Store\nRequest Store\nSession Cache)]
        Postgres[(PostgreSQL :5432\nAudit Log\npgvector Memory)]
        Kafka([Kafka :9092\nEvent Broker])
        flagd[flagd :8013\nOpenFeature Flags]
    end

    subgraph Agent Runtime — AI Agents Module opt-in
        Worker[RequestConsumer\nasyncio background task]
        Orch[AgentOrchestrator\nPerception → Reason → Act]
        Harness[HarnessCoordinator\nPlanner / Generator / Evaluator]
        Guardrails[Guardrails\nL1 PII Filter\nL2 Injection Guard\nL3 Action Limits\nL4 Audit Logger]
        HITL[HITL Gateway\nApproval workflow]
        LLM[Anthropic Claude\nLLM API]
    end

    subgraph Observability
        OTel[OTel Collector :4317]
        Prometheus[Prometheus :9090]
        Grafana[Grafana :3000]
        Jaeger[Jaeger :16686]
    end

    Client -->|POST /v1/requests 202| API
    Client -->|GET /v1/requests/:id| API
    Client -->|POST /v1/hitl/:id/decide| API

    API -->|save RequestState| Redis
    API -->|publish domain.request.created| Kafka

    Kafka -->|consume| Worker
    Worker --> Orch
    Orch -->|harness_mode != solo| Harness
    Harness -->|per-sprint P→R→A| Orch

    Orch --> Guardrails
    Guardrails -->|masked context| LLM
    Guardrails --> HITL

    HITL -->|store approval request| Redis
    HITL -->|immutable record| Postgres
    HITL -->|publish decision event| Kafka

    API -->|read RequestState| Redis
    Orch -->|audit log| Postgres
    Orch -->|vector recall| Postgres

    flagd -->|autonomy level| Orch

    Orch -->|traces + metrics + logs| OTel
    API -->|traces + metrics| OTel
    OTel --> Prometheus
    OTel --> Jaeger
    Prometheus --> Grafana
```

---

## Request Lifecycle (Happy Path — with AI Agents Module enabled)

> This diagram shows the full flow **when the AI Agents Module is active**.
> Without it, the pipeline ends after the API publishes to Kafka and the
> `RequestConsumer` processes the request directly without LLM/HITL involvement.

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant Store as RequestStore (Redis)
    participant Broker as Kafka
    participant Worker as RequestConsumer
    participant Orch as AgentOrchestrator
    participant Guard as Guardrails
    participant LLM as Claude LLM
    participant HITL as HITL Gateway
    participant Audit as Audit Logger (PG)

    C->>API: POST /v1/requests {context}
    API->>Guard: mask_dict(context) [PII L1-L4]
    API->>Store: save(RequestState queued)
    API->>Broker: publish domain.request.created
    API-->>C: 202 Accepted {request_id}

    Broker->>Worker: consume event
    Worker->>Store: update status → processing
    Worker->>Orch: run_cycle(context)

    Orch->>Guard: L1 PII filter
    Orch->>Guard: L2 injection guard
    Orch->>Guard: L3 action limits
    Orch->>Guard: L4 audit write (before-execute)
    Orch->>LLM: reason(masked context)
    LLM-->>Orch: proposed action + risk_score

    alt risk_score < 0.4 HOTL
        Orch->>Orch: execute immediately
        Orch->>Broker: publish agent.action.executed
    else risk_score >= 0.4 HITL
        Orch->>HITL: request_approval(action, risk_score)
        HITL->>Store: store HITLRequest (TTL 3600s)
        HITL->>Broker: publish agent.action.proposed
        Note over HITL: Blocks until decision or timeout
        C->>API: POST /v1/hitl/:id/decide {APPROVE/REJECT}
        API->>HITL: record_decision()
        HITL->>Audit: immutable decision record
        HITL->>Broker: publish agent.action.approved
    end

    Orch->>Store: update status → completed
    C->>API: GET /v1/requests/:id
    API->>Store: get(request_id)
    API-->>C: 200 {status: completed, result: ...}
```

---

## Harness Mode Selection _(AI Agents Module only)_

> Only relevant when the AI Agents Module is enabled. See `specs/ai/harness-design.md`
> for the full sprint loop diagram.

| Mode         | When to use                          | Cost multiplier |
| ------------ | ------------------------------------ | --------------- |
| `solo`       | Single-step, clear scope, < 20 min   | 1×              |
| `simplified` | Feature-level, 30 min – 2 h          | 5–10×           |
| `full`       | Multi-feature, ambiguous scope, 2 h+ | 15–25×          |

Controlled by `settings.harness_mode` (default: `solo`).

---

## Infrastructure Fallback Pattern

Every infra dependency has an in-memory fallback for local dev:

| Production             | Local fallback         | Blocked in production?          | Module             |
| ---------------------- | ---------------------- | ------------------------------- | ------------------ |
| `RedisRequestStore`    | `InMemoryRequestStore` | No                              | Core               |
| `KafkaEventBroker`     | `InMemoryBroker`       | No                              | Core               |
| `HITLRedisStore`       | `InMemoryHITLStore`    | No                              | AI Agents (opt-in) |
| `PostgresAuditStorage` | `InMemoryAuditStorage` | **Yes** — raises `RuntimeError` | AI Agents (opt-in) |

---

## Key Module Map

### Core

| Layer         | Module                            | Role                              |
| ------------- | --------------------------------- | --------------------------------- |
| API           | `src/api/rest/main.py`            | FastAPI app, lifespan wiring      |
| Routers       | `src/api/rest/routers/`           | `requests`, `health`              |
| Worker        | `src/workers/request_consumer.py` | Asyncio background consumer       |
| Config        | `src/shared/config.py`            | All settings via Pydantic         |
| Observability | `src/observability/`              | OTel, Prometheus, structured logs |

### AI Agents Module _(opt-in — only when `src/agents/` is present)_

| Layer         | Module                                    | Role                                     |
| ------------- | ----------------------------------------- | ---------------------------------------- |
| Routers       | `src/api/rest/routers/hitl.py`            | HITL approval endpoint                   |
| Orchestrator  | `src/agents/orchestrator/orchestrator.py` | P→R→A loop                               |
| Harness       | `src/agents/harness/coordinator.py`       | Planner/Generator/Evaluator              |
| HITL          | `src/agents/hitl_gateway.py`              | Approval workflow                        |
| Guardrails    | `src/guardrails/`                         | PII, injection, limits, audit            |
| Memory        | `src/memory/`                             | Vector store, session cache, bug history |
| Feature Flags | `src/shared/feature_flags.py`             | Autonomy levels via OpenFeature          |
