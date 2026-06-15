# ADR-0077 — Idempotency Keys for Write Endpoints

**Status:** Accepted
**Date:** 2026-06-14
**Authors:** Valdomiro Souza
**Spec:** specs/api/SPEC-API-002-idempotency-keys.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0009](ADR-0009-caching-strategy.md) (caching), [ADR-0075](ADR-0075-resilience-fallback-policy.md) (degrade-open), [ADR-0076](ADR-0076-api-structured-error-model-and-correlation.md) (error envelope), [ADR-0024](ADR-0024-api-versioning-strategy.md) (versioning)

## Context

`POST /v1/requests` creates a new request — a new `request_id`, a new Kafka event, eventually a new
agent run and audit record — on every call. Clients that retry after a timeout, and proxies that
replay, therefore create **duplicate** work and audit noise. HTTP has a conventional remedy (the
`Idempotency-Key` header) that the API did not implement. SPEC-API-002 specifies it; this ADR records
the design.

## Decision

1. **Opt-in `Idempotency-Key` header on `POST /v1/requests`.** Absent ⇒ behaviour unchanged
   (backward-compatible). Present and valid (printable ASCII, 8–200 chars) ⇒ idempotent semantics.
2. **Claim-then-act with a fingerprint.** A new `IdempotencyStore` atomically claims the key
   (`SET NX EX <ttl>`) storing `{request_id, fingerprint, created_at}`, where
   `fingerprint = sha256(salt + masked-body-json)`:
   - fresh key ⇒ process normally and record;
   - repeat key + **matching** fingerprint ⇒ replay the original `202` (same `request_id`), no new
     event/audit;
   - repeat key + **different** fingerprint ⇒ `422 IDEMPOTENCY_KEY_REUSED` (a published, additive
     error code, ADR-0024/0076).
3. **Degrade-open store** (ADR-0075): `RedisIdempotencyStore` in production, `InMemoryIdempotencyStore`
   fallback when Redis is down — mirrors the request/HITL store selection. Under fallback, correctness
   is per-instance and best-effort, logged as a degradation.
4. **No PII stored.** Only a salted hash of the **masked** body plus the `request_id` (both ≤ L3).
5. **TTL via config** (`idempotency_ttl_hours`, default 24h), aligned with `request_result_ttl_hours`.
6. **Reuses the SPEC-API-001 error envelope** — no new error shape.

## Consequences

### Positive

- Safe client retries; no duplicate agent runs or audit rows from replays.
- Atomic claim prevents the race where two identical requests both create work.
- Sets a reusable pattern for future write endpoints.

### Negative / Trade-offs

- **Per-instance fallback.** During a Redis outage, idempotency holds only within one process. Accepted
  as degrade-open — failing the POST closed would hurt availability more (ADR-0075).
- A small write-path cost (one claim op) and a stored record per key for the TTL window.

### Neutral

- Idempotency is opt-in, so existing clients are unaffected until they adopt the header.

## Alternatives Considered

- **Fail-closed on Redis outage.** Rejected — worse availability than degrade-open for a create path.
- **Dedup at the consumer only.** Rejected — the consumer already guards reprocessing, but that does
  not stop a _second submission_ from creating a second request_id/event; the dedup must be at submit.
- **Natural idempotency via a client-supplied request_id.** Rejected — couples the resource id to the
  client and complicates collision handling; a separate header with a fingerprint is cleaner.

## Compliance & Risk

- **Controls affected:** OWASP A04 (design) — strengthened; A09 (no duplicate/forgeable audit).
- **Data classification impact:** none new; fingerprint hashes masked body, key is L3 (ADR-0012).
- **Autonomy impact:** none — no `src/agents/` or `src/guardrails/` change; no AI-safety phase.
- **Review/expiry:** permanent; revisit if write endpoints multiply (generalise the dependency).

## Related

- `specs/api/SPEC-API-002-idempotency-keys.md`
- `docs/api/api-standards.md` (Idempotency — Target → Current)
- `src/agents/request_store.py` (store pattern) · `docs/adr/adr-review-checklist.md`
