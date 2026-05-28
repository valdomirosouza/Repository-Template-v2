# domain-service

**Language:** Java 21 / Spring Boot 3.3 | **Type:** API | **Port:** 8080  
**Owner:** domain-team | **Spec:** `services.yaml`

Core business logic service. Consumes `request.created.v1` events, manages `DomainEntity`
lifecycle, and publishes `domain.entity.created.v1` / `domain.entity.updated.v1`.

## Quick start

```bash
# From the monorepo root (requires infra-up):
make run-java SERVICE=domain-service

# Tests (no Docker required):
make test-unit-java SERVICE=domain-service

# Full test suite (integration — requires infra):
make test-java SERVICE=domain-service
```

## Environment variables

| Variable                  | Default                                  | Required          |
| ------------------------- | ---------------------------------------- | ----------------- |
| `DATABASE_URL`            | `jdbc:postgresql://localhost:5432/appdb` | Yes in production |
| `DATABASE_USER`           | `appuser`                                | Yes in production |
| `DATABASE_PASSWORD`       | `placeholder-set-in-env`                 | Yes               |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092`                         | Yes in production |
| `KAFKA_CONSUMER_GROUP`    | `domain-service-group`                   | No                |

## Kafka topics

| Direction | Topic                      | Schema                                                                             |
| --------- | -------------------------- | ---------------------------------------------------------------------------------- |
| Consumes  | `request.created.v1`       | `infrastructure/message-broker/schema-registry/avro/request-created-v1.avsc`       |
| Publishes | `domain.entity.created.v1` | `infrastructure/message-broker/schema-registry/avro/domain-entity-created-v1.avsc` |
| Publishes | `domain.entity.updated.v1` | `infrastructure/message-broker/schema-registry/avro/domain-entity-updated-v1.avsc` |

## REST API

| Method | Path                          | Description                |
| ------ | ----------------------------- | -------------------------- |
| `POST` | `/v1/entities`                | Create a new domain entity |
| `GET`  | `/v1/entities/{id}`           | Get entity by ID           |
| `GET`  | `/v1/entities?status=PENDING` | List entities by status    |
| `POST` | `/v1/entities/{id}/activate`  | Activate an entity         |
| `GET`  | `/actuator/health`            | Health probe               |
| `GET`  | `/actuator/prometheus`        | Prometheus metrics         |
