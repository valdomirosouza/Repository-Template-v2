# ADR-0005 — Message Broker Selection

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead

---

## Context

The async event topology defined in ADR-0003 requires a message broker that supports:

- Durable, ordered event log per topic partition
- Schema enforcement to prevent producer/consumer contract drift
- At-least-once delivery with consumer-side idempotency support
- Retention long enough for event replay (audit, recovery, backfill)
- Horizontal scaling via partition assignment

---

## Decision

Adopt **Apache Kafka** (self-hosted on Kubernetes via Strimzi operator) with
**Confluent Schema Registry** for Avro schema management.

Configuration defaults:

| Parameter            | Value        | Rationale                                      |
| -------------------- | ------------ | ---------------------------------------------- |
| Retention            | 7 days       | Covers HITL timeout window (1h) + audit replay |
| Replication factor   | 3            | Tolerate 1 broker failure in production        |
| Min in-sync replicas | 2            | No silent data loss on broker failure          |
| Partition count      | 12 (default) | Allows up to 12 parallel consumers per group   |
| Acks                 | `all`        | Producer waits for all ISR acknowledgement     |
| Schema compatibility | BACKWARD     | Consumers always understand new messages       |

Topics and schemas: `docs/api/asyncapi/v1/asyncapi.yaml`
Schema files: `infrastructure/message-broker/schema-registry/avro/`

---

## Consequences

### Positive

- Kafka's replicated, durable log supports event replay — critical for audit recovery
  and agent debugging after a HITL expiry incident.
- Avro + Schema Registry enforces backward compatibility at publish time, not at
  consumer rollout — prevents silent schema drift.
- Strimzi on Kubernetes integrates with the Helm-based deployment strategy (ADR-0006).
- Consumer group offset management supports independent scaling of agent pools.

### Negative / Trade-offs

- Kafka + ZooKeeper (or KRaft) adds significant operational complexity vs. a managed queue.
- Minimum viable cluster requires 3 brokers for production replication factor.
- Schema Registry is a single point of coordination — must be HA-deployed.

---

## Alternatives Considered

**RabbitMQ**
Rejected: no native event log / replay; message durability weaker than Kafka's replicated log;
AMQP routing flexibility is not needed for this point-to-point topology.

**Redis Streams**
Rejected: weaker durability (AOF async by default); no native schema enforcement;
consumer group semantics less mature than Kafka's; limited ecosystem for large-scale replay.

**AWS SQS + SNS**
Rejected: cloud-vendor lock-in inconsistent with multi-cloud deployment strategy (ADR-0006);
no native schema registry integration; SQS max retention 14 days but with less replay ergonomics.

**NATS JetStream**
Rejected: smaller ecosystem; less operational tooling maturity vs. Kafka in 2025;
no widely-adopted schema registry equivalent.
