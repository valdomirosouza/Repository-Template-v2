# ADR-0019 — Redis TLS and Value Encryption

**Status:** Accepted
**Date:** 2026-05-28
**Authors:** Security Lead, DPO
**Spec:** `specs/privacy/redis-tls.md`

---

## Context

The 2026-05-28 security audit found two gaps in Redis security:

1. **Plaintext TCP**: Redis connections transmit all data unencrypted — pending
   HITL decisions, session memory, and rate-limit state are visible to anyone
   on the cluster network with access to the Redis port.

2. **Plaintext values at rest**: `HITLRedisStore` serialises full `HITLRequest`
   objects (including `context_summary` and `action_parameters`) as unencrypted
   JSON. Even after PII masking, these fields may contain L2 identifiers.

LGPD Art. 46 and GDPR Art. 32 require appropriate technical measures to protect
personal data, including in intermediate storage such as cache layers.

---

## Decision

### Transport: TLS for all Redis connections

Enforce TLS via two settings: `redis_tls_enabled` (bool) and `redis_tls_ca_cert`
(path to CA cert). Production startup is blocked when `redis_tls_enabled=False`
and `app_env=production`.

In production, the `REDIS_URL` must use the `rediss://` scheme; `redis_tls_enabled`
acts as an additional enforcement check independent of the URL scheme.

### Value encryption: HITLRedisStore

Reuse `EncryptedField` (AES-256-GCM, `src/shared/db_encryption.py`, ADR-0018) to
encrypt the **entire serialised JSON payload** of each `HITLRequest` before writing
to Redis. The same `DB_ENCRYPTION_KEY` is used — acceptable because it is a general
application-layer encryption key, not a DB-specific secret.

Encrypting the full payload (rather than selected fields) ensures no field is missed
as the `HITLRequest` schema evolves.

`EncryptedField` is injected as an optional constructor argument to `HITLRedisStore`,
following the same pattern as `PostgresVectorStore` (ADR-0018). This keeps the store
testable without a real key.

---

## Consequences

### Positive

- All data in transit between the app pod and Redis is encrypted (TLS)
- Pending HITL decisions at rest in Redis are AES-256-GCM encrypted
- `EncryptedField.decrypt()` passthrough path ensures zero-downtime rollout
  over existing unencrypted rows
- No new secret introduced — reuses `DB_ENCRYPTION_KEY` (ADR-0008 rotation
  schedule: 180 days)

### Negative / Trade-offs

- `redis_tls_enabled=True` adds TLS handshake overhead to every Redis operation
  (~0.5 ms per connection establishment; amortised by connection pooling)
- `fakeredis` in unit tests does not support TLS — tests use `HITLRedisStore`
  with `encryption=None` or `encryption=EncryptedField(test_key)` over
  plaintext `fakeredis`
- `SessionMemory` Redis encryption is deferred to ADR-0020 (lower risk than HITL
  store; sprint context contains no L1/L2 PII by definition after masking)

---

## Alternatives Considered

**Redis AUTH + network policy only**
Rejected: AUTH protects against unauthenticated access but does not encrypt
traffic in transit — a compromised network device still reads plaintext.

**Managed Redis with vendor-side at-rest encryption (AWS ElastiCache, GCP Memorystore)**
Considered: vendor encryption at rest protects persistent RDB files but relies
on the vendor's key management. Application-layer encryption (chosen approach)
protects against a compromised cloud provider account or storage media. Both
are not mutually exclusive — the chosen approach layers on top of vendor encryption.

**Per-field encryption of context_summary and action_parameters only**
Rejected in favour of full-payload encryption: field-by-field encryption requires
maintaining an explicit list of sensitive fields and re-auditing on every schema
change. Full-payload encryption is simpler and safer.
