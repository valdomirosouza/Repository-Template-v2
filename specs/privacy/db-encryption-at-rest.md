# Spec: Database Encryption at Rest

**ID:** SPEC-db-encryption-at-rest
**Status:** Accepted
**Version:** 1.0.0
**Date:** 2026-05-28
**Authors:** Security Lead, DPO
**ADR:** ADR-0018 (Database Encryption at Rest)
**DPIA reference:** `docs/privacy/dpia/dpia-v1.md` — AES-256 requirement §4.2

---

## 1. Purpose

Enforce the AES-256 at-rest encryption requirement stated in the DPIA (§4.2) and RIPD
for all L1 and L2 PII stored in PostgreSQL. Specifically: the `content` column of
`agent_memory_documents` (which may retain context derived from user interactions)
and the `metadata` column of `audit_events` (which stores action parameters).

---

## 2. Scope

| Table                    | Column     | PII Classification     | Why                                                                   |
| ------------------------ | ---------- | ---------------------- | --------------------------------------------------------------------- |
| `agent_memory_documents` | `content`  | L2 (masked context)    | May contain residual user context after PII masking                   |
| `audit_events`           | `metadata` | L2 (action parameters) | Parameters may include L2 identifiers (usernames, session references) |

Columns **not** in scope: embeddings (float vectors, no PII), `source`, `tags`,
`event_type`, `agent_id`, `outcome` — these contain no personal data.

---

## 3. Encryption Design

### 3.1 Algorithm

**AES-256-GCM** (Galois/Counter Mode)

- 256-bit key (32 bytes)
- 96-bit random nonce per encryption call
- 128-bit authentication tag (included in output)
- Provides both confidentiality and integrity (authenticated encryption)
- Reusing a nonce with the same key is catastrophic — `os.urandom(12)` prevents this

### 3.2 Wire Format

Encrypted values stored in the database follow this format:

```
enc:v1:<base64url-encoded(nonce[12 bytes] || ciphertext_with_tag)>
```

- `enc:` sentinel — allows decrypt() to detect unencrypted values during migration
- `v1` — key version identifier; enables key rotation without downtime
- nonce and ciphertext are concatenated before base64 encoding (no separator needed)

**Example (not a real value):**

```
enc:v1:aBcDeFgHiJkL0123456789abcdefghijklmnopqrstuvwxyz==
```

### 3.3 Key Management

| Environment | Key source                                                                                                |
| ----------- | --------------------------------------------------------------------------------------------------------- |
| Production  | Vault (KV v2, path `secret/data/app/db-encryption-key`) — injected via Vault Agent as `DB_ENCRYPTION_KEY` |
| Staging     | Vault (separate namespace)                                                                                |
| Local dev   | `DB_ENCRYPTION_KEY` in `.env` — a dev-only key, never shared with production                              |

Key must be exactly 32 bytes encoded as 64 lowercase hexadecimal characters.

Generate a new key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3.4 Key Rotation

The `v1` version prefix in the wire format enables zero-downtime rotation:

1. Generate a new key (v2).
2. Add `DB_ENCRYPTION_KEY_V2` to Vault alongside the existing `DB_ENCRYPTION_KEY` (v1).
3. Deploy an app version that reads both keys: decrypts with v1 or v2, always encrypts with v2.
4. Run the key-rotation migration job (`make db-reencrypt`) to re-encrypt all existing rows with v2.
5. Remove `DB_ENCRYPTION_KEY` (v1) from Vault once migration job completes.

Key rotation does **not** require any table schema changes or downtime.

---

## 4. Implementation

### 4.1 EncryptedField utility

`src/shared/db_encryption.py` — a standalone class with no framework dependencies:

```python
class EncryptedField:
    def encrypt(self, plaintext: str) -> str: ...   # → enc:v1:<base64>
    def decrypt(self, value: str) -> str: ...        # plaintext passthrough if not encrypted
    @staticmethod
    def is_encrypted(value: str) -> bool: ...
```

The `decrypt()` method accepts both encrypted (`enc:v1:...`) and plaintext values,
allowing a rolling deployment to read rows written before encryption was enabled.

### 4.2 PostgresVectorStore integration

`PostgresVectorStore` accepts an optional `EncryptedField` dependency:

```python
PostgresVectorStore(pool, encryption=EncryptedField(settings.db_encryption_key))
```

- `upsert()` calls `encryption.encrypt(doc.content)` before INSERT
- `search()` calls `encryption.decrypt(row["content"])` after SELECT
- When `encryption` is `None` (local dev without Vault), the store operates without encryption — blocked in `app_env=production` (see §4.3)

### 4.3 Production guard

`Settings.reject_placeholder_secrets()` raises `ValueError` if
`DB_ENCRYPTION_KEY` contains `"placeholder"` and `app_env=production`.

`DB_ENCRYPTION_ENABLED=false` is only valid when `app_env != production`.

---

## 5. Alembic Migrations

| Revision | Name                            | Purpose                                                                               |
| -------- | ------------------------------- | ------------------------------------------------------------------------------------- |
| `0002`   | `enable_pgcrypto_vector`        | Enables `pgcrypto` and `vector` PostgreSQL extensions                                 |
| `0003`   | `create_agent_memory_documents` | Creates `agent_memory_documents` table (the `content` column stores encrypted values) |

The `content` column schema is `TEXT` — the `enc:v1:...` wire format is a text string.
No schema change is needed when enabling encryption on an existing table; only the
application logic changes. For `audit_events.metadata`, encryption is applied in a
separate migration once an in-place re-encryption migration job is written.

---

## 6. SQL Injection Fix

While implementing this spec, a SQL injection vulnerability was identified and fixed
in `PostgresVectorStore._SEARCH`:

```python
# BEFORE (vulnerable — source_filter concatenated into SQL string):
where = f"WHERE source = '{source_filter}'" if source_filter else ""

# AFTER (parameterized queries):
_SEARCH_FILTERED = "... WHERE source = $3 ..."
rows = await conn.fetch(_SEARCH_FILTERED, embedding_str, k, source_filter)
```

---

## 7. Acceptance Criteria

- [ ] `EncryptedField.encrypt()` never produces the same output for the same input (nonce uniqueness)
- [ ] `EncryptedField.decrypt()` returns original plaintext after roundtrip
- [ ] `EncryptedField.decrypt()` returns plaintext as-is (passthrough — migration path)
- [ ] Invalid key length raises `ValueError` with a descriptive generation command
- [ ] Corrupted ciphertext raises `cryptography.exceptions.InvalidTag`
- [ ] `PostgresVectorStore` encrypts on write and decrypts on read when `encryption` is provided
- [ ] `DB_ENCRYPTION_KEY=placeholder` blocks startup in `app_env=production`
- [ ] SQL injection in `PostgresVectorStore._SEARCH` eliminated
- [ ] Unit test coverage ≥ 80%
- [ ] `0002` and `0003` migrations run cleanly on a fresh database
