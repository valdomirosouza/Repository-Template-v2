# event-worker

**Language:** Go 1.23 | **Type:** Worker | **Port:** 9091 (metrics)
**Owner:** platform-team | **Spec:** `services.yaml`

High-throughput stateless Kafka consumer. Consumes entity domain events and publishes
`event.processed.v1` downstream.

## Quick start

```bash
# From the monorepo root (requires infra-up):
make run-go SERVICE=event-worker

# Unit tests (no Docker required):
make test-unit-go SERVICE=event-worker

# Lint:
make lint-go SERVICE=event-worker
```

## Environment variables

| Variable                      | Default                    | Required          |
| ----------------------------- | -------------------------- | ----------------- |
| `KAFKA_BOOTSTRAP_SERVERS`     | `localhost:9092`           | Yes in production |
| `KAFKA_CONSUMER_GROUP`        | `event-worker-group`       | No                |
| `KAFKA_TOPIC_ENTITY_CREATED`  | `domain.entity.created.v1` | No                |
| `KAFKA_TOPIC_ENTITY_UPDATED`  | `domain.entity.updated.v1` | No                |
| `KAFKA_TOPIC_EVENT_PROCESSED` | `event.processed.v1`       | No                |
| `PROMETHEUS_PORT`             | `9091`                     | No                |

## Kafka topics

| Direction | Topic                      | Schema                                                                             |
| --------- | -------------------------- | ---------------------------------------------------------------------------------- |
| Consumes  | `domain.entity.created.v1` | `infrastructure/message-broker/schema-registry/avro/domain-entity-created-v1.avsc` |
| Consumes  | `domain.entity.updated.v1` | `infrastructure/message-broker/schema-registry/avro/domain-entity-updated-v1.avsc` |
| Publishes | `event.processed.v1`       | `infrastructure/message-broker/schema-registry/avro/event-processed-v1.avsc`       |
