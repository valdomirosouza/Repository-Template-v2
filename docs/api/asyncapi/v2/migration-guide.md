# AsyncAPI Schema Evolution — Migration Guide

**Owner:** Tech Lead | **Status:** Active | **Last updated:** 2026-05-28
**ADR:** ADR-0024 (API Versioning Strategy)
**Applies to:** `docs/api/asyncapi/v1/asyncapi.yaml` and all Avro schemas in `infrastructure/message-broker/schema-registry/avro/`

---

## Purpose

This guide documents how Kafka event schemas evolve in this monorepo: what changes are allowed within v1, what requires a new major version, and the migration process when a breaking change is unavoidable.

All consumers must follow the compatibility rules in ADR-0024 §2. The rules here translate those principles into concrete steps.

---

## Stability Annotations in asyncapi.yaml

Each channel in `v1/asyncapi.yaml` carries two extension fields:

| Extension field | Type   | Values                             | Meaning                                                  |
| --------------- | ------ | ---------------------------------- | -------------------------------------------------------- |
| `x-stability`   | string | `stable` \| `beta` \| `deprecated` | Current maturity level of this channel's contract        |
| `x-sunset-date` | string | ISO-8601 date or `null`            | Date after which the channel will no longer be published |

**Stable** — contract is frozen; only backwards-compatible additions allowed.
**Beta** — contract may evolve; consumers should expect optional field additions.
**Deprecated** — channel will be removed on the `x-sunset-date`; consumers must migrate before that date.

These fields are machine-readable. CI can warn when the current date is within 30 days of a `x-sunset-date`.

---

## Backwards-Compatible Changes (allowed within v1)

The following changes may be made to an existing channel or Avro schema without creating a new major version:

| Change                                   | Example                                    | Consumer impact                                 |
| ---------------------------------------- | ------------------------------------------ | ----------------------------------------------- |
| Add optional field with a default value  | Add `correlation_id?: string` to a payload | Existing consumers ignore the new field         |
| Add a new event type (new topic)         | Add `domain.entity.archived` channel       | Consumers that don't subscribe are unaffected   |
| Expand an enum with a new value          | Add `MEDIUM` to a priority enum            | Consumers must map unknown values to a sentinel |
| Change a field description or example    | Clarify what `masked_feedback` means       | Documentation only; no wire change              |
| Add a new message to an existing channel | New `oneof` variant in a shared Avro union | Existing consumers skip unrecognised variants   |

After any backwards-compatible change:

1. Bump the Avro schema version in Schema Registry.
2. Update `asyncapi.yaml` with the new field.
3. Update the relevant `*.avsc` file under `infrastructure/message-broker/schema-registry/avro/`.
4. Update `CHANGELOG.md`.

---

## Breaking Changes (require a new major version)

| Change                                    | Why it breaks                                              |
| ----------------------------------------- | ---------------------------------------------------------- |
| Remove a field from an existing payload   | Consumers that read the field receive `null` unexpectedly  |
| Rename a field                            | Consumers that read the old name receive `null`            |
| Change a field's type (e.g. string → int) | Deserialisation fails at the consumer boundary             |
| Make an optional field required           | Old producers that omit the field produce invalid messages |
| Remove a topic                            | Consumers that subscribe get no messages; may stall        |
| Change the Avro subject name/namespace    | Schema Registry compatibility check fails                  |

---

## Breaking Change Migration Process

Follow these steps when a breaking change is unavoidable:

### Step 1 — Get approval

File an RFC (`skills/change-management/rfc-process.md`). The RFC must include:

- Affected channel(s) and field(s)
- All known consumers and their migration timeline
- The proposed new topic name (format: `<base-topic>.v2`)
- The proposed dual-publish start and sunset dates

Approval requires: Tech Lead + all consuming service owners (see `services.yaml`).

### Step 2 — Create v2 schema and channel

1. Create a new Avro schema file: `<schema-name>-v2.avsc` in `infrastructure/message-broker/schema-registry/avro/`.
2. Register it in Schema Registry under a new subject (`<topic>.v2-value`).
3. Add the new channel to `asyncapi.yaml` (e.g., `domain.request.created.v2`).
4. Mark the old channel as `deprecated` and set `x-sunset-date`.

### Step 3 — Dual-publish period (≥ 1 sprint)

The producer publishes to **both** the old topic and the new topic simultaneously.

```python
# Example: dual-publish during migration
await broker.publish("domain.request.created", old_envelope, key=request_id)
await broker.publish("domain.request.created.v2", new_envelope, key=request_id)
```

Consumers migrate to the new topic during this window.

### Step 4 — Sunset the old topic

After all consumers have migrated (verified by Kafka consumer group lag = 0 on the old topic):

1. Remove the dual-publish from the producer code.
2. Remove the old channel from `asyncapi.yaml`.
3. Set `x-sunset-date` to today's date in the archived entry in this migration guide.
4. Update `services.yaml` to reflect the new topic name.
5. Update `CHANGELOG.md`.

---

## Current v1 Channel Stability Status

| Channel                   | Stability | Sunset date | Notes                                      |
| ------------------------- | --------- | ----------- | ------------------------------------------ |
| `domain.request.created`  | stable    | null        |                                            |
| `agent.action.proposed`   | stable    | null        |                                            |
| `agent.action.approved`   | stable    | null        |                                            |
| `agent.action.rejected`   | stable    | null        |                                            |
| `agent.action.expired`    | stable    | null        | Timeout = auto-reject invariant (ADR-0011) |
| `agent.action.executed`   | stable    | null        |                                            |
| `domain.result.completed` | stable    | null        |                                            |
| `agent.feedback.applied`  | beta      | null        | Feedback loop spec may evolve (Wave 7+)    |
| `audit.event.written`     | stable    | null        | Append-only; immutable invariant           |
| `agent.harness.state`     | beta      | null        | Proto-backed; harness design may evolve    |

---

## Consumer Implementation Requirements

All consumers of v1 channels must:

1. **Ignore unknown fields** — do not fail if a field appears that is not in the known schema.
2. **Map unknown enum values to a sentinel** — e.g., `UNKNOWN` or `UNRECOGNISED`, not an exception.
3. **Monitor the `x-sunset-date`** — subscribe to CHANGELOG.md updates or CI notifications.
4. **Test with the latest schema** — run `make test-python` after any Avro schema bump to
   catch deserialisation regressions early.

---

## v2 Planning Candidates

The following channels are flagged as candidates for a future v2 migration based on known
roadmap items. No action is required until an RFC is filed.

| Channel                  | Potential breaking change                                                     | Tracking |
| ------------------------ | ----------------------------------------------------------------------------- | -------- |
| `agent.feedback.applied` | Adding `user_segment` field may require DPIA review before it can be optional | Wave 8+  |
| `agent.harness.state`    | Proto-to-Avro alignment if harness moves to cross-service deployment          | Wave 9+  |
