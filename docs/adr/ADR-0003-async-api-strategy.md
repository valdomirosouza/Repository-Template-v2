# ADR-0003 — Async API Strategy

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead

---

## Context

The system processes high-volume, latency-tolerant flows (agent task dispatch, result delivery,
audit events) alongside low-volume, latency-sensitive flows (HITL approval, health checks).
A single synchronous API cannot serve both efficiently.

Requirements:

- Decouple producers from consumers to allow independent scaling
- Preserve message order within a partition (per-entity consistency)
- Support event replay for audit, debugging, and recovery
- Provide a machine-readable contract for all event schemas

---

## Decision

Adopt **Apache Kafka** as the message broker with **AsyncAPI 2.6** as the specification
format and **Apache Avro** (via Confluent Schema Registry) for schema enforcement.

Synchronous REST (FastAPI) is used only for:

- Direct user queries with sub-second latency requirements
- HITL approval submission and status polling
- Health and readiness endpoints

All high-volume, agent-internal, and observability flows use async Kafka events.

### Core event topology

| Topic                     | Producer      | Consumer        | Key          |
| ------------------------- | ------------- | --------------- | ------------ |
| `domain.request.created`  | API Gateway   | Agent Service   | `entity_id`  |
| `agent.action.proposed`   | Agent Service | HITL Gateway    | `agent_id`   |
| `agent.action.approved`   | HITL Gateway  | Agent Service   | `request_id` |
| `agent.action.rejected`   | HITL Gateway  | Agent Service   | `request_id` |
| `agent.action.expired`    | HITL Gateway  | Agent Service   | `request_id` |
| `agent.action.executed`   | Agent Service | Audit, Notifier | `agent_id`   |
| `domain.result.completed` | Agent Service | API Gateway     | `entity_id`  |
| `audit.event.written`     | Audit Logger  | SIEM / archival | `agent_id`   |

Contract files: `docs/api/asyncapi/v1/asyncapi.yaml`

---

## Consequences

### Positive

- Producers and consumers scale independently — agent pool size is decoupled from API throughput.
- Kafka's log compaction and configurable retention (7 days default) enable event replay for debugging and audit.
- AsyncAPI 2.6 spec generates documentation and client stubs, keeping contracts machine-verifiable.
- Avro schema registry enforces backward compatibility — consumers never receive an unrecognised field.

### Negative / Trade-offs

- Adds operational complexity (Kafka cluster, Schema Registry, topic management).
- Eventual consistency: callers must poll or subscribe for results; not suitable for sub-second sync flows.
- Schema evolution requires coordination between producer and consumer teams.

---

## Alternatives Considered

**REST polling (synchronous)**
Rejected: tight coupling between API and Agent Service; horizontal scaling of agents requires load balancer changes; no native event replay.

**GraphQL subscriptions (WebSocket)**
Rejected: stateful WebSocket connections complicate horizontal scaling and require sticky sessions; not suitable for async agent-internal flows.

**Redis Streams**
Rejected: weaker durability guarantees (AOF async) relative to Kafka's replicated log; no native Schema Registry integration; limited partition semantics.

**Google Cloud Pub/Sub / AWS SNS+SQS**
Rejected: cloud-vendor lock-in; self-hosted Kafka on Kubernetes aligns with multi-cloud deployment strategy (ADR-0006).
