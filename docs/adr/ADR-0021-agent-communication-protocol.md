# ADR-0021 — Agent Communication Protocol

**Status:** Accepted
**Date:** 2026-05-28
**Authors:** Tech Lead
**Spec:** `specs/ai/harness-design.md §2, §9`
**Supersedes:** None | **Superseded by:** None

---

## Context

The multi-agent harness (ADR-0014) has three communicating roles — Planner, Generator,
and Evaluator. Their messages are currently Python dataclasses defined in
`src/agents/harness/models.py`:

```python
TaskBrief → SprintContract → GeneratorArtifact → EvaluatorScore → HarnessResult
```

These dataclasses are Python-only and serialised as JSON when written to the audit log
or published to Kafka. There is no schema enforcement at the boundary between agents:

1. A Generator can return a `GeneratorArtifact` missing `sprint_id` and the Evaluator
   will only discover the error at runtime.
2. The Kafka harness state topic (`agent.harness.state`) publishes `HarnessStateEnvelope`
   as protobuf (defined in `infrastructure/proto/harness_state.proto`) but the Python
   code serialises to JSON — the proto is not yet used on the wire.
3. No versioning strategy exists for message schema evolution.

As the harness is extended to support multi-service deployments and the Go event-worker
(Wave 1), a formal inter-agent contract is required.

---

## Decision

### 1. Canonical schema: Protocol Buffers

Protobuf is the canonical schema for all inter-agent messages that cross a process
boundary (Kafka topics, gRPC calls). Python dataclasses remain valid for in-process
passing within a single service.

**Why Protobuf over alternatives:**

| Option      | Reason not chosen                                                                                                                     |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| JSON Schema | No binary encoding; schema validation is advisory, not enforced by the serialiser                                                     |
| Apache Avro | Already used for domain events (ADR-0005); keeping agent messages separate avoids schema registry coupling for internal harness state |
| MessagePack | No schema enforcement; no multi-language codegen                                                                                      |
| Protobuf    | Binary, versioned, multi-language codegen (Python, Go, Java), backwards-compatible field addition                                     |

### 2. Proto file location and ownership

All agent message schemas live in `infrastructure/proto/harness_state.proto`.
The file is owned by the Tech Lead — changes require a PR review from Security Lead
when new fields could carry PII.

**Codegen targets:**

```bash
make gen-proto-python   # → src/shared/generated/grpc/
make gen-proto-go       # → api/grpc/  (for event-worker integration)
```

CI verifies stubs are up-to-date (`ci-go.yml` proto drift check).

### 3. Message boundary policy

| Boundary                          | Protocol                          | Schema enforcement                             |
| --------------------------------- | --------------------------------- | ---------------------------------------------- |
| In-process (same Python service)  | Python dataclasses (`models.py`)  | Type hints + mypy strict                       |
| Kafka topic `agent.harness.state` | Protobuf (`HarnessStateEnvelope`) | `ParseFromString` raises on malformed messages |
| gRPC (future multi-service)       | Protobuf                          | gRPC framework enforces schema at call time    |
| Audit log                         | JSON (derived from dataclasses)   | mypy + `test_harness_contracts.py`             |
| HITL gateway                      | JSON (in-process)                 | mypy strict                                    |

### 4. Versioning strategy

Protobuf field numbers are **permanent** — once assigned they cannot be reused.

| Change type                     | Allowed?       | Process                                                      |
| ------------------------------- | -------------- | ------------------------------------------------------------ |
| Add optional field (new number) | Yes            | PR + codegen regeneration                                    |
| Rename a field                  | Yes            | Rename only in proto; wire format unchanged                  |
| Change field type               | No             | Create a new field; deprecate old with `[deprecated = true]` |
| Remove a field                  | No             | Mark `reserved N;` to prevent number reuse                   |
| Add a new message               | Yes            | PR + codegen regeneration                                    |
| Add a `oneof` arm               | Yes, with care | Existing consumers ignore unknown arms                       |

### 5. PII invariant

All string fields in `harness_state.proto` that may contain user content are masked
before serialisation. The proto comments document this requirement per field.
`pii_filter.mask_text()` must be called on `masked_feedback`, `masked_previous_approach_summary`,
and `masked_proposed_alternative` before setting those fields.

**Enforcement:** `tests/contract/test_harness_contracts.py` asserts that
`HarnessStateEnvelope` fields marked `masked_*` are always set via the filter.

### 6. Migration from JSON to Protobuf on Kafka

The `agent.harness.state` topic currently receives no messages (feature not yet activated).
When activated, messages will be Protobuf from day one. No migration of existing messages
is required.

For services already consuming the topic in JSON (none currently): a dual-publish period
of one sprint is required before the JSON publisher is removed.

---

## Consequences

### Positive

- Schema violations detected at serialisation time, not at consumer runtime
- Go event-worker can consume harness state events using generated Go stubs
- Field addition is backwards-compatible — consumers ignore unknown fields
- PII masking requirement is codified in the schema file, not just convention

### Negative / Trade-offs

- Protobuf binary is not human-readable — debugging requires `protoc --decode` or a
  Protobuf-aware log viewer
- Codegen must be re-run and committed on every proto change — adds friction to schema
  evolution
- Java domain-service cannot yet consume harness state (stubs not generated for Java)
  — deferred until Java service needs this data

---

## Alternatives Considered

**Keep JSON + JSON Schema validation**
Rejected: JSON Schema validation is opt-in and advisory; malformed messages still reach
consumers. Binary Protobuf enforces schema at the boundary.

**Avro via Schema Registry (consistent with domain events)**
Considered: Avro and Schema Registry add operational complexity for a component that
is currently single-service. Revisit if harness state events need to be consumed
by the domain-service or event-worker.
