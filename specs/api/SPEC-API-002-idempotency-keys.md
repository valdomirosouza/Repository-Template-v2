---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-API-002
title: Idempotency keys for POST endpoints
version: 0.1.0
status: implemented # draft | in-review | approved | implemented | superseded
owner: valdomirosouza
created: 2026-06-14
source: Improvement plan Wave 4 — docs/api/api-standards.md "Idempotency — Target"; issue #251
deployment_topology: monorepo-services
governing_adrs: [ADR-0009, ADR-0019, ADR-0024, ADR-0076]
new_adrs_required: [api-idempotency-keys]
related_specs:
  [
    specs/api/SPEC-API-001-error-model-and-request-correlation.md,
    specs/system/request-pipeline.md,
  ]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-API-002 — Idempotency keys for POST endpoints

> **One-line scope.** Let clients safely retry `POST /v1/requests` by sending an `Idempotency-Key`;
> a repeated key returns the original request's result instead of creating a duplicate.

## How `/deliver` reads this spec (section → phase)

| Spec section            | Feeds /deliver phase(s)         | Gate                          |
| ----------------------- | ------------------------------- | ----------------------------- |
| §1–§4                   | 0 Intake · 1 Conception         | problem/value/risk            |
| §5 FR, §6 NFR           | 2 Discovery · 4 Specification   | FR→AC traceability            |
| §7, §14, new_adrs       | 5 Architecture                  | ADR authored & accepted       |
| §8 Interface Contracts  | 4 Specification · 6 Development | contract-driven dev (OpenAPI) |
| §9 Data Model           | 6 Development                   | key/TTL convention            |
| §12 Acceptance Criteria | 8 Testing                       | test evidence                 |

---

## 1. Context & Problem

### 1.1 Problem statement

`POST /v1/requests` creates a new request (new `request_id`, new Kafka event) on **every** call. A
client that times out and retries — or a proxy that replays — creates **duplicate** work: duplicate
agent runs, duplicate audit events, duplicate side effects. There is no way for a client to say "this
is the same submission as before." `docs/api/api-standards.md` lists idempotency keys as a Target.

### 1.2 Research / product question

Can a client retry a create safely and get exactly-once semantics for the submission, with a minimal,
storage-backed mechanism that degrades gracefully when Redis is down?

### 1.3 Why now / motivation

Retries are inevitable (network, proxies, client libraries). Establishing the `Idempotency-Key`
contract now — reusing the request store and the SPEC-API-001 error envelope — closes a correctness
gap and sets the pattern for future write endpoints.

### 1.4 Deployment topology decision

`monorepo-services` — implemented in the existing api-gateway (`src/api/rest/`).

## 2. Goals & Success Metrics

| ID   | Goal                                                  | Measure of success                                                   |
| ---- | ----------------------------------------------------- | -------------------------------------------------------------------- |
| G-01 | A retried POST with the same key creates no duplicate | Same key ⇒ same `request_id`, exactly one Kafka event, one audit row |
| G-02 | Idempotency is opt-in and backward-compatible         | Requests without the header behave exactly as today                  |
| G-03 | Conflicting reuse is rejected, not silently wrong     | Same key + different body ⇒ 422 `IDEMPOTENCY_KEY_REUSED`             |

## 3. Non-Goals / Out of Scope

- **Not** idempotency for GET (already safe) or for the HITL decision endpoint (separate, has its own
  PENDING-state guard).
- **Not** a global exactly-once guarantee across the async pipeline — only de-duplication of the
  **submission** (the consumer already guards reprocessing, see request-pipeline.md).
- **Not** cross-region replication of the idempotency store.

## 4. Consumers & Personas

| Consumer         | Need                                               |
| ---------------- | -------------------------------------------------- |
| API client / SDK | Retry a create safely after a timeout              |
| Frontend         | Avoid double-submitting on a flaky connection      |
| SRE              | No duplicate agent runs / audit noise from retries |

## 5. Functional Requirements

| ID    | Requirement (EARS)                                                                                                                                                                                     |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-01 | WHEN a POST `/v1/requests` carries a valid `Idempotency-Key` not seen before, the system SHALL process it normally and record `key → {request_id, request fingerprint}` with a TTL.                    |
| FR-02 | WHEN a POST repeats an `Idempotency-Key` already recorded **with a matching request fingerprint**, the system SHALL skip processing and return the original `202` response (same `request_id`).        |
| FR-03 | WHEN a POST repeats an `Idempotency-Key` with a **different** request fingerprint, the system SHALL return `422` with code `IDEMPOTENCY_KEY_REUSED` and not process it.                                |
| FR-04 | The system SHALL validate the key (printable ASCII, 8–200 chars); an invalid key SHALL return `422 VALIDATION_ERROR`.                                                                                  |
| FR-05 | WHEN no `Idempotency-Key` is supplied, behaviour SHALL be unchanged (a new request every time).                                                                                                        |
| FR-06 | The key record SHALL claim atomically (set-if-absent) so two concurrent identical requests do not both create work; the loser SHALL return the winner's `request_id`.                                  |
| FR-07 | WHEN the idempotency store (Redis) is unavailable, the system SHALL fall back to in-memory (degrade-open, ADR-0075) and log the degradation; correctness across instances is best-effort in that mode. |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                             |
| ------ | ------------------------------------------------------------------------------------------------------- |
| NFR-01 | Lookup/claim adds ≤ 2 ms p99 to the POST path.                                                          |
| NFR-02 | Coverage ≥ 80% for the new store + handler logic (CLAUDE.md §3.5).                                      |
| NFR-03 | TTL via config (`idempotency_ttl_hours`, default 24h) — no magic numbers.                               |
| NFR-04 | The fingerprint SHALL be a salted hash of the masked request body — **no PII** stored (ADR-0012).       |
| NFR-05 | The stored value (request_id + fingerprint) is L3; encrypt only if it were to hold L1/L2 (it does not). |
| NFR-06 | Reuse the SPEC-API-001 error envelope for 422/409 — no new error shape.                                 |

## 7. Architecture

```
POST /v1/requests  ──►  IdempotencyStore.claim(key, fingerprint)
                          │  claimed (new)        │  exists+match        │ exists+mismatch
                          ▼                        ▼                      ▼
                    process + record          replay original 202    422 IDEMPOTENCY_KEY_REUSED
```

- New `IdempotencyStore` (`src/api/rest/idempotency.py` or `src/agents/idempotency_store.py`) mirrors
  the request-store pattern: `RedisIdempotencyStore` (SET NX + TTL) and `InMemoryIdempotencyStore`,
  selected by the same Redis-availability logic as the request/HITL stores (ADR-0075).
- Stored value: `{request_id, fingerprint, created_at}` under key
  `{idempotency_redis_key_prefix}:key:{key}`.
- Fingerprint = `sha256(salt + masked_body_json)` — detects "same key, different body".
- The router resolves the store via a dependency (like `get_request_store`).

## 8. Interface Contracts _(gate: contract-driven dev)_

| Method | Path         | New header               | Behaviour                                             |
| ------ | ------------ | ------------------------ | ----------------------------------------------------- |
| POST   | /v1/requests | `Idempotency-Key` (opt.) | replay original 202 on match; 422 on mismatch/invalid |

OpenAPI: document the optional `Idempotency-Key` request header and the new
`IDEMPOTENCY_KEY_REUSED` code in `components/schemas/Error` enum (additive, ADR-0024). Regenerate the
TS client (`make gen-api-client-ts`).

## 9. Data Model

### 9.1 Entities

`IdempotencyRecord { request_id: str, fingerprint: str (sha256 hex), created_at: datetime }`.

### 9.2 Storage key/schema convention

`{idempotency_redis_key_prefix}:key:{idempotency_key}` → JSON record, written with `SET NX EX <ttl>`
(atomic claim). In-memory fallback: a dict with the same claim semantics.

### 9.3 Retention

TTL = `idempotency_ttl_hours` (default 24h), aligned with `request_result_ttl_hours` so a key lives at
least as long as its result is retrievable.

## 10. Golden Signals & SLO Definitions

| Signal     | Derivation                             | Exposed as     |
| ---------- | -------------------------------------- | -------------- |
| Traffic    | POSTs with/without key; replays vs new | counter labels |
| Errors     | `IDEMPOTENCY_KEY_REUSED` rate          | error_rate     |
| Saturation | unchanged                              | —              |

No new SLO threshold; add a `requests_idempotent_replays_total` counter (optional) for visibility.

## 11. Governance, Privacy & Security

| Concern      | Control                                                       | Maps to         |
| ------------ | ------------------------------------------------------------- | --------------- |
| PII          | fingerprint hashes the **masked** body; key not PII (FR-04)   | ADR-0012        |
| Auditability | replays do not create new audit rows (the point)              | ADR-0026        |
| Abuse        | key length-bounded; per-key claim is O(1); honours rate limit | threat-model.md |
| Availability | degrade-open to in-memory when Redis down                     | ADR-0075        |

STRIDE on the new `Idempotency-Key` input: Tampering — validated/bounded; a forged key only ever
returns the caller's own prior result or a 422. No `src/agents/`/`src/guardrails/` change → no Phase 10.

## 12. Acceptance Criteria _(gate: dry-run validation)_

| ID    | Acceptance criterion (WHEN … THEN …)                                                                                         | Covers FR(s) |
| ----- | ---------------------------------------------------------------------------------------------------------------------------- | ------------ |
| AC-01 | WHEN POST with a fresh key, THEN 202 and the key is recorded with the request fingerprint.                                   | FR-01        |
| AC-02 | WHEN the same key + same body is POSTed again, THEN the same `request_id` is returned and no second event/audit is produced. | FR-02        |
| AC-03 | WHEN the same key + different body is POSTed, THEN 422 with code `IDEMPOTENCY_KEY_REUSED`.                                   | FR-03        |
| AC-04 | WHEN the key is too short/long/non-ASCII, THEN 422 `VALIDATION_ERROR`.                                                       | FR-04        |
| AC-05 | WHEN no key is supplied, THEN two POSTs create two distinct `request_id`s (unchanged).                                       | FR-05        |
| AC-06 | WHEN two identical keyed requests race, THEN exactly one is processed and both return the same id.                           | FR-06        |

> **Requirement coverage footer (gate).** 7 FRs total · 7 mapped to ≥ 1 AC · **0 unmapped ✅**
> (FR-07 degrade-open verified via the in-memory store path in AC-01/02).

## 13. Risks & Limitations

- **In-memory fallback is per-instance** — under Redis outage, idempotency holds only within one
  process (documented; degrade-open per ADR-0075). Acceptable: the alternative (fail-closed on POST)
  is worse for availability.
- **Fingerprint collisions** — sha256 over masked body; collision risk negligible.

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0009 (caching/Redis), ADR-0019 (Redis TLS/encryption), ADR-0024 (versioning),
  ADR-0076 (error envelope).
- **Adds:** one ADR — _"Idempotency keys for write endpoints"_ (`new_adrs_required: api-idempotency-keys`).
- **Produces:** `IdempotencyStore` + router wiring, config keys, OpenAPI header + code, regenerated TS
  client, tests, and a promotion of the `api-standards.md` Idempotency section Target → Current.

## 15. Open Questions

1. Scope keys by auth subject as well (`subject:key`) to prevent cross-tenant key guessing? (Lean: yes
   when auth is mandatory; for the template, key-only with a note.)
2. Return a `Idempotency-Replayed: true` response header on a replay? (Lean: yes — cheap observability.)

## 16. References

- `docs/api/api-standards.md` (Idempotency — Target) · `specs/api/SPEC-API-001-...md` (error envelope)
- `src/agents/request_store.py` (store pattern) · `src/api/rest/routers/requests.py` (POST handler)
- ADR-0075 (degrade-open fallback) · IETF draft "The Idempotency-Key HTTP Header Field"
