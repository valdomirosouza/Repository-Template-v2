# Redis Key Standards

> **Owner:** Platform / SRE | **Status:** Living standard
> The naming, TTL, and encryption rules for Redis keys. Redis holds **operational state** (request
> lifecycle, pending HITL queue) with the in-memory fallbacks used when it is down (ADR-0075). The
> key patterns are also summarised in `docs/data/data-model-catalog.md`; this is the focused standard.

In production Redis uses `rediss://` + TLS and value encryption for sensitive payloads (ADR-0019).

---

## Naming convention

```
{prefix}:{entity}:{id}        # e.g. hitl:request:550e8400-…
{prefix}:{collection}         # e.g. hitl:pending  (a sorted set)
```

- **Prefix** is configurable, never hard-coded: `hitl_redis_key_prefix` (default `hitl`),
  `request_redis_key_prefix` (default `request`) — `src/shared/config.py`.
- Lowercase, colon-delimited segments; the last segment of an entity key is the UUID.
- One key shape per access pattern; don't overload a key with multiple meanings.

## Key catalog

| Key pattern                  | Type       | Holds                             | TTL (config)                      | Encrypted    |
| ---------------------------- | ---------- | --------------------------------- | --------------------------------- | ------------ |
| `hitl:request:{request_id}`  | string     | active HITL request (JSON)        | `hitl_redis_ttl_grace_hours` (4h) | ✓ if key set |
| `hitl:pending`               | sorted set | pending ids, score = `expires_at` | —                                 | n/a          |
| `hitl:expired:{request_id}`  | string     | archived/expired HITL request     | `hitl_expired_ttl_days` (7d)      | ✓ if key set |
| `request:state:{request_id}` | string     | request lifecycle state (JSON)    | `request_result_ttl_hours` (24h)  | —            |

Sources: `src/agents/hitl_store.py`, `src/agents/request_store.py`.

## Rules

- **Always set a TTL** on operational keys (no unbounded growth); the values above come from config,
  not magic numbers in code.
- **Encrypt sensitive payloads** before writing: HITL request payloads in production must be written
  through an `EncryptedField` (AES-256-GCM) — never store unencrypted HITL payloads in prod (ADR-0019,
  CLAUDE.md §3.2). The store accepts an optional `encryption` dependency; decrypt is passthrough-safe
  to allow zero-downtime rollout over unencrypted rows.
- **TLS in production:** `rediss://`, `redis_tls_enabled=true` (`reject_placeholder_secrets` enforces
  this before a prod deploy).
- **Fallback:** when Redis is down, `InMemoryHITLStore` / `InMemoryRequestStore` take over
  (degrade-open, ADR-0075) — keep key logic in the store classes so both paths stay consistent.

## Testing

- Assert TTLs are set on write (a key without a TTL is a leak).
- Verify encryption-at-write for HITL payloads in production config.
- Cover fallback parity (in-memory vs Redis behave the same) — `skills/engineering/testing-strategy.md`.

## Related

- `docs/data/data-model-catalog.md` · `docs/data/data-classification.md`
- ADR-0019 (Redis TLS + value encryption) · ADR-0075 (fallback policy)
- `src/agents/hitl_store.py` · `src/agents/request_store.py` · `src/shared/config.py`
