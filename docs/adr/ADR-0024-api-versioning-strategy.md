# ADR-0024 — API Versioning Strategy

**Status:** Accepted
**Date:** 2026-05-28
**Authors:** Tech Lead, Platform Lead
**Spec:** `specs/api/async-api-design.md`, `specs/system/async-event-flow.md`
**Supersedes:** None | **Superseded by:** None

---

## Context

The monorepo exposes three distinct API surfaces:

1. **REST** (`docs/api/openapi/v1/openapi.yaml`) — external-facing; consumed by the frontend and third-party clients.
2. **AsyncAPI / Kafka events** (`docs/api/asyncapi/v1/asyncapi.yaml`) — internal event bus; consumed by domain-service, event-worker, and observability tooling.
3. **gRPC** (`infrastructure/proto/`) — service-to-service RPCs; consumed by api-gateway, event-worker, and batch-jobs.

As the system evolves, these contracts must change without breaking existing consumers. Previously:

- REST versioning was implicit (all routes are `/v1/` with no defined upgrade path).
- AsyncAPI had a single `v1` file with no migration strategy or forward-compatibility annotations.
- gRPC proto evolution was covered by ADR-0021 §4 (field numbers are permanent) but only for
  the harness messages. Service-level RPCs (`domain_service.proto`, `event_worker.proto`) were
  added in Wave 6 without a documented versioning policy for RPC surfaces.

This ADR establishes a unified versioning policy across all three surfaces.

---

## Decision

### 1. REST Versioning

**Scheme:** URL-based major version prefix (`/v1/`, `/v2/`).

| Rule                                                                                          | Rationale                                          |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Breaking changes require a new major version                                                  | Consumers cannot be forced to update on a timeline |
| Non-breaking additions (new fields, new paths) are backwards-compatible within a version      | JSON parsers ignore unknown fields                 |
| Deprecated endpoints are announced via `Deprecation` and `Sunset` response headers (RFC 8594) | Gives consumers a grace period                     |
| Old version supported for ≥ 2 sprints after the new version ships                             | Defined in SLO/error-budget-policy.md              |

**What is a breaking change in REST:**

- Removing or renaming a field in a response body
- Changing the type of an existing field
- Removing an endpoint
- Making a previously optional request field required
- Changing an HTTP status code for an existing response type
- Changing authentication or authorization requirements for an existing endpoint

**What is NOT a breaking change:**

- Adding a new optional field to a response body
- Adding a new optional field to a request body
- Adding a new endpoint
- Expanding an enum with new values (consumers must handle unknown values gracefully)

### 2. AsyncAPI / Kafka Event Versioning

**Scheme:** Avro schema version via Schema Registry + topic name suffix for major breaks.

| Change type                     | Allowed within v1?    | Process                                          |
| ------------------------------- | --------------------- | ------------------------------------------------ |
| Add optional field with default | Yes (backward-compat) | PR + Schema Registry version bump                |
| Add required field              | No                    | New major version; topic rename to `*.v2`        |
| Remove field                    | No                    | New major version; topic rename to `*.v2`        |
| Change field type               | No                    | New major version; topic rename to `*.v2`        |
| Rename field                    | No                    | Alias in Schema Registry + new major version     |
| Add new event type (new topic)  | Yes                   | PR + asyncapi.yaml update + services.yaml update |

**Dual-publish period:** When a topic is renamed to `*.v2`, the old topic is published to
for one full sprint (≥ 1 week) after the new topic is live. Consumers are expected to migrate
within that window. After the sunset date, the old publisher is removed.

**Forward-compatibility annotations in asyncapi.yaml:** Each channel that has a known
breaking-change candidate is annotated with `x-stability` and `x-sunset-date` extension
fields so tooling can surface deprecation warnings. See `docs/api/asyncapi/v1/asyncapi.yaml`
for the annotation schema.

### 3. gRPC / Protobuf Versioning

Inherits the Protobuf field-level rules from ADR-0021 §4 and extends them to cover
service-level (RPC) versioning.

**Field-level rules (from ADR-0021):**

| Change                          | Allowed?       | Process                                                |
| ------------------------------- | -------------- | ------------------------------------------------------ |
| Add optional field (new number) | Yes            | PR + codegen regeneration + codegen commit             |
| Rename a field                  | Yes            | Rename in proto only; wire format unchanged            |
| Change field type               | No             | New field number; old field marked `[deprecated=true]` |
| Remove a field                  | No             | Mark `reserved N;` to prevent number reuse             |
| Add `oneof` arm                 | Yes, carefully | Existing consumers ignore unknown arms                 |

**Service-level rules (new in this ADR):**

| Change                                     | Allowed within v1? | Process                                                          |
| ------------------------------------------ | ------------------ | ---------------------------------------------------------------- |
| Add a new RPC method                       | Yes                | PR + codegen + update relevant service client                    |
| Add optional request field                 | Yes                | Backward-compatible; existing callers send old shape             |
| Remove an RPC method                       | No                 | Mark as `deprecated` in comment; sunset via new `.proto` version |
| Rename an RPC method                       | No                 | New method + deprecation comment on old method                   |
| Change request/response message (breaking) | No                 | New message type; update RPC signatures                          |

**Proto package versioning:** When a breaking service change is required, the package is
bumped (`domainservice.v1` → `domainservice.v2`) and a new `.proto` file is created. Old
and new packages are generated simultaneously during the dual-support period.

**Codegen commit requirement:** Generated stubs (`src/shared/generated/grpc/`,
`services/event-worker/api/grpc/`) must be committed alongside proto changes.
CI (`ci.yml`, `ci-go.yml`) verifies stubs are up to date.

### 4. Consumer-Side Compatibility Requirements

All consumers of these APIs must:

1. **Ignore unknown JSON fields** in REST responses (do not fail on new fields).
2. **Ignore unknown Protobuf fields** when deserialising (this is the default Protobuf behaviour).
3. **Handle unknown Avro enum values** gracefully (map to a sentinel `UNKNOWN` value, not an error).
4. **Implement the `Sunset` header** — when a REST endpoint sets `Sunset: <date>`, consumers
   must log a warning and plan migration before that date.

These requirements are verified via contract tests (ADR-0022, Wave 6 Pact contracts).

### 5. Versioning Governance

| Surface  | Who approves a breaking change           | Notice period             |
| -------- | ---------------------------------------- | ------------------------- |
| REST     | Tech Lead + Product Owner                | ≥ 2 sprints               |
| AsyncAPI | Tech Lead + all consuming service owners | ≥ 1 sprint (dual-publish) |
| gRPC     | Tech Lead                                | ≥ 1 sprint (dual-compile) |

Breaking changes to any surface require:

1. An RFC (`skills/change-management/rfc-process.md`) for Normal changes.
2. A new ADR if the change requires a package/topic/major version bump.
3. An updated `docs/dependency-manifest.yaml` entry for the old version sunset date.

---

## Consequences

### Positive

- Consumers can safely adopt new fields without gating on a coordinated release.
- Sunset dates are machine-readable (`x-sunset-date` extension, `Sunset` headers), enabling
  automated deprecation tracking in CI.
- Proto field permanence and reserved field rules prevent accidental wire breakage.
- Unified governance table eliminates ambiguity about who approves API changes.

### Negative / Trade-offs

- Dual-publish periods for Kafka events add short-term operational complexity.
- URL-based REST versioning means multiple route prefixes must be maintained during migration.
  For the current scale (one frontend consumer), this is low overhead.
- Committing generated stubs adds repository churn on every proto change. This is accepted:
  the alternative (dynamic codegen at build time) adds build-time latency and requires all
  services to have `protoc` available in CI.

---

## Alternatives Considered

**Header-based REST versioning (`Accept: application/vnd.v2+json`):**
Rejected for this template. URL versioning is more visible, easier to test in a browser,
and easier to reason about in logs. Header versioning adds complexity without benefit at
the current scale.

**Schema Registry for gRPC (Confluent):**
Considered alongside the existing Avro + Schema Registry for Kafka. Rejected: gRPC schema
validation is handled by the proto compiler and `ParseFromString` at the boundary, which
is sufficient. Adding Schema Registry for gRPC would couple two unrelated serialisation
systems.

**Semantic versioning for proto packages (`v1.2.3`):**
Considered. Rejected: proto packages use major-only versioning (`v1`, `v2`) by convention
in the Buf ecosystem and Google API design guidelines. Minor/patch changes are
backwards-compatible within a major version, so tracking them in the package name adds noise.
