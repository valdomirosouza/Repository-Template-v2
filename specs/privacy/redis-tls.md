# Spec: Redis TLS and Value Encryption

**ID:** SPEC-redis-tls
**Status:** Accepted
**Version:** 1.0.0
**Date:** 2026-05-28
**Authors:** Security Lead, DPO
**ADR:** ADR-0019 (Redis TLS and Value Encryption)

---

## 1. Purpose

Close two at-rest and in-transit security gaps for Redis:

1. **In-transit**: Redis connections use plaintext TCP — all data (HITL pending
   decisions, session memory, rate-limit state) is visible on the network.
2. **At-rest**: Pending HITL requests stored in Redis contain `context_summary`
   and `action_parameters`, which may include L2 PII residuals even after masking.

Both gaps were identified in the 2026-05-28 security audit and flagged as HIGH risk.

---

## 2. Scope

| Store                           | Key sensitivity                                                          | Fix                                                    |
| ------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------ |
| `HITLRedisStore`                | **HIGH** — contains `context_summary`, `action_parameters`, `risk_score` | TLS + value encryption                                 |
| `RedisRequestStore`             | LOW — status enum + timestamps                                           | TLS only                                               |
| `SessionMemory`                 | MEDIUM — sprint context                                                  | TLS + value encryption (future — deferred to ADR-0020) |
| Rate-limit counters (`slowapi`) | NONE                                                                     | TLS only                                               |

---

## 3. TLS Connection

### 3.1 Configuration

| Setting             | Type | Default | Description                                         |
| ------------------- | ---- | ------- | --------------------------------------------------- |
| `redis_tls_enabled` | bool | `False` | Enable TLS for Redis connections                    |
| `redis_tls_ca_cert` | str  | `""`    | Path to CA certificate file for server verification |

In production, the Redis URL must use the `rediss://` scheme (Redis SSL).
`redis_tls_enabled=True` enables TLS when using a `redis://` URL with a
TLS-terminating proxy.

Production startup validation: `redis_tls_enabled` must be `True` when
`app_env=production`.

### 3.2 Redis client construction

```python
redis_kwargs: dict[str, Any] = {
    "max_connections": settings.redis_max_connections,
    "decode_responses": True,
}
if settings.redis_tls_enabled or settings.redis_url.startswith("rediss://"):
    redis_kwargs["ssl"] = True
    if settings.redis_tls_ca_cert:
        redis_kwargs["ssl_ca_certs"] = settings.redis_tls_ca_cert

client = redis_async.from_url(settings.redis_url, **redis_kwargs)
```

---

## 4. Value Encryption (HITLRedisStore)

### 4.1 Strategy

Encrypt the **entire serialised JSON payload** of each `HITLRequest` before it
is written to Redis, and decrypt after retrieval. This approach:

- Protects all fields uniformly — no risk of missing a new field when the schema evolves
- Reuses `EncryptedField` from `src/shared/db_encryption.py` (AES-256-GCM, ADR-0018)
- The same `DB_ENCRYPTION_KEY` is reused — this is acceptable because the key is
  a general application-layer secret, not DB-specific. Reduces key proliferation.

### 4.2 HITLRedisStore interface

```python
class HITLRedisStore:
    def __init__(
        self,
        client: Any,
        encryption: EncryptedField | None = None,
    ) -> None: ...
```

Internal helpers:

```python
def _to_redis(self, request: HITLRequest) -> str:
    payload = self._serialize(request)
    return self._encryption.encrypt(payload) if self._encryption else payload

def _from_redis(self, data: str) -> HITLRequest:
    payload = self._encryption.decrypt(data) if self._encryption else data
    return self._deserialize(payload)
```

The `EncryptedField.decrypt()` passthrough path handles any unencrypted rows
written before encryption was enabled (rolling deployment safety).

### 4.3 Production guard

The `main.py` lifespan constructs `HITLRedisStore` with an `EncryptedField` when
`db_encryption_enabled=True` (same flag as DB encryption — both require the key).
If the flag is `False` in `app_env=production`, startup is blocked.

---

## 5. Acceptance Criteria

- [ ] `redis_tls_enabled=True` causes `ssl=True` in `from_url()` kwargs
- [ ] `redis_tls_ca_cert` is passed as `ssl_ca_certs` when set
- [ ] `redis_tls_enabled=False` in production triggers `ValueError` at startup
- [ ] `HITLRedisStore` with `EncryptedField`: stored bytes are not readable as plain JSON
- [ ] `HITLRedisStore` without `EncryptedField`: backward-compat path still works
- [ ] Save → get roundtrip preserves all `HITLRequest` fields with encryption
- [ ] Unit test coverage ≥ 80% for new paths
