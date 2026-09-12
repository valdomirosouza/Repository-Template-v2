---
id: SPEC-API-005
kind: spec
status: approved # draft | in-review | approved | implemented | superseded (ADR-0085)
status_source: body-header:Approved # carried by migrate_spec_frontmatter.py, never promoted
owner: Tech Lead
issue: null # GitHub issue number that delivered/owns this spec
governing_adrs: 
  - ADR-0003
  - ADR-0005
  - ADR-0012
implemented_by:
  - docs/api/asyncapi/v1/asyncapi.yaml
  - src/shared/broker.py
  - services.yaml
verified_by: 
  - tests/integration/test_kafka_events.py
related_specs: []
last_updated: 2026-09-12
---

# Async API Design

**Status:** Approved | **Owner:** Tech Lead | **Last updated:** 2026-05-24
**ADR references:** ADR-0003 (Async API Strategy), ADR-0005 (Message Broker Selection)

---

## Overview

This spec governs the design of all asynchronous event contracts in the system.
It complements `specs/system/async-event-flow.md` (which describes the runtime flow)
by specifying the **design rules** that all event producers and consumers must follow.

Machine-readable contracts: `docs/api/asyncapi/v1/asyncapi.yaml`

---

## Design Principles

1. **Event-first for high-volume flows** — any flow processing > 10 req/s must use
   Kafka events, not synchronous REST calls (ADR-0003).
2. **Schema-first** — every event type must have an Avro schema registered in the
   Schema Registry before the first producer is deployed.
3. **Backward compatibility** — all schema changes must be `BACKWARD` compatible.
   Adding optional fields is allowed. Removing or renaming fields requires a new
   event type with a migration window.
4. **PII masked before publish** — no event payload reaches Kafka without passing
   through `src/guardrails/pii_filter.py` (ADR-0012, three mandatory interception points).
5. **Idempotent consumers** — every consumer must handle duplicate delivery
   (at-least-once semantics). Use `event_id` for deduplication.

---

## Event Envelope

All events share a common envelope. Domain-specific fields go in `payload`.

```json
{
  "event_id": "<uuid v4>",
  "event_type": "<domain>.<entity>.<verb>",
  "schema_version": "1.0",
  "produced_at": "<ISO8601 UTC>",
  "trace_id": "<W3C traceparent>",
  "producer_service": "<service-name>",
  "payload": {}
}
```

| Field              | Type    | Required | Notes                                     |
| ------------------ | ------- | -------- | ----------------------------------------- |
| `event_id`         | UUID    | Yes      | Stable deduplication key for consumers    |
| `event_type`       | string  | Yes      | Dot-separated: `domain.entity.verb`       |
| `schema_version`   | string  | Yes      | Semver; must match registered Avro schema |
| `produced_at`      | ISO8601 | Yes      | UTC timestamp of production               |
| `trace_id`         | string  | Yes      | W3C `traceparent` for distributed tracing |
| `producer_service` | string  | Yes      | Service name for debugging                |
| `payload`          | object  | Yes      | Domain-specific fields; all PII masked    |

---

## Topic Naming Convention

```
<domain>.<entity>.<verb>
```

Examples:

- `domain.request.created`
- `agent.action.proposed`
- `audit.event.written`

Rules:

- All lowercase, dot-separated
- No hyphens or underscores in topic names
- Verb is past tense (event = something that happened)

---

## Event Catalogue

| Event type                | Topic                     | Producer      | Consumer(s)     | Schema file                |
| ------------------------- | ------------------------- | ------------- | --------------- | -------------------------- |
| `domain.request.created`  | `domain.request.created`  | API Gateway   | Agent Service   | `avro/domain_request.avsc` |
| `agent.action.proposed`   | `agent.action.proposed`   | Agent Service | HITL Gateway    | `avro/agent_action.avsc`   |
| `agent.action.approved`   | `agent.action.approved`   | HITL Gateway  | Agent Service   | `avro/hitl_decision.avsc`  |
| `agent.action.rejected`   | `agent.action.rejected`   | HITL Gateway  | Agent Service   | `avro/hitl_decision.avsc`  |
| `agent.action.expired`    | `agent.action.expired`    | HITL Gateway  | Agent Service   | `avro/hitl_decision.avsc`  |
| `agent.action.executed`   | `agent.action.executed`   | Agent Service | Audit, Notifier | `avro/agent_action.avsc`   |
| `domain.result.completed` | `domain.result.completed` | Agent Service | API Gateway     | `avro/domain_result.avsc`  |
| `audit.event.written`     | `audit.event.written`     | Audit Logger  | SIEM / archival | `avro/audit_event.avsc`    |

**Lifecycle (W11-T2, issue #347).** Every topic above is registered in `services.yaml` with a
`lifecycle:` of `active` (published by in-tree code), `planned` (in the contract, no publisher
yet: `agent.action.executed`, `domain.result.completed`, `audit.event.written`,
`agent.harness.state`) or `reference`. The Java/Go reference pipeline uses the `.v1`-suffixed
topics (`request.created.v1`, `hitl.decision.v1`, `audit.event.v1`, `domain.entity.created.v1`,
`domain.entity.updated.v1`, `event.processed.v1`), also registered and carried in
`docs/api/asyncapi/v1/asyncapi.yaml`. `scripts/governance/check_topic_contract.py` fails CI when
the registry, the contract and the topic literals in code disagree.

Schema files location: `infrastructure/message-broker/schema-registry/avro/`

---

## PII Handling in Events

All event payloads must be masked before publish. The three mandatory interception
points (ADR-0012) apply to event production:

```python
from src.guardrails.pii_filter import mask_dict

safe_payload = mask_dict(raw_payload)
await producer.send(topic, value=envelope(safe_payload))
# raw_payload must never be sent directly
```

Verify in tests:

```python
# In any producer test: assert no PII reaches the mock broker
assert "fake@example.com" not in str(captured_event)
assert "[EMAIL]" in str(captured_event)
```

---

## Consumer Implementation Requirements

Every consumer must implement:

1. **Idempotency check** — look up `event_id` in a deduplication store before processing
2. **Dead letter queue (DLQ)** — unprocessable events go to `<topic>.dlq` with error context
3. **Structured logging** — log `event_id`, `event_type`, `trace_id` on receipt and completion
4. **OTel span** — create a child span with `messaging.kafka.message.offset` attribute

---

## Testing Requirements

- Unit tests must use a mock broker (no real Kafka dependency)
- Integration tests (`tests/integration/test_kafka_events.py`) use an `InMemoryProducer` stub
  for structural assertions (envelope, PII masking, naming); tests marked `@pytest.mark.integration`
  also run against a real Kafka instance in CI (provided by the `test-integration` job services block)
- Every producer test must assert that the emitted payload contains no unmasked PII fields
