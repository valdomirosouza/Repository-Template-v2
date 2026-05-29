# Runbook: Database Encryption Key Rotation

**Topic:** Rotating `DB_ENCRYPTION_KEY` without downtime
**Severity:** Operational — run annually or immediately after a key exposure incident
**Owner:** Security Lead + SRE Lead

---

## Overview

The application uses AES-256-GCM field-level encryption (`src/shared/db_encryption.py`).
The wire format is `enc:v1:<base64(nonce+ciphertext)>`. The `v1` prefix was designed to
support zero-downtime key rotation: new rows are encrypted with the new key (future `v2`
prefix), old rows are decrypted with the old key (passthrough logic already in `decrypt()`).

---

## When to rotate

- **Scheduled:** annually, or per your key management policy
- **Emergency:** immediately if `DB_ENCRYPTION_KEY` is suspected to have been exposed
  (leaked secret, compromised CI runner, terminated employee with access)

---

## Before you start

```bash
# Verify current encryption is active
psql $DATABASE_URL -c "SELECT content FROM agent_memory_documents LIMIT 1;"
# Should return: enc:v1:<base64> — if plaintext, encryption is not active

# Back up the database before any rotation
pg_dump $DATABASE_URL > backup-pre-rotation-$(date +%Y%m%d).sql

# Generate the new key (must be 64 hex characters = 32 bytes = AES-256)
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "New key: $NEW_KEY"
# Store this in your secret manager BEFORE proceeding
```

---

## Rotation procedure

### Step 1 — Implement `enc:v2:` support (development task)

The current `EncryptedField` class uses a hardcoded `v1` prefix. To support dual-key
rotation, add a second `EncryptedField` instance and update `decrypt()` to try both keys:

```python
# Wire in lifespan:
old_ef = EncryptedField(old_key)
new_ef = EncryptedField(new_key)

def decrypt_with_fallback(value: str) -> str:
    try:
        return new_ef.decrypt(value)
    except Exception:
        return old_ef.decrypt(value)  # fallback to old key for legacy rows
```

This allows reads to succeed during the migration window when both old and new rows exist.

### Step 2 — Deploy the new key

1. Add `DB_ENCRYPTION_KEY_NEW=<new_key>` alongside the existing `DB_ENCRYPTION_KEY` in
   your secrets manager
2. Deploy the updated application that supports dual-key decryption
3. Verify readiness: `curl http://localhost:8000/ready`

### Step 3 — Re-encrypt existing rows

Run the re-encryption migration script (write one specific to your schema):

```python
# Example for agent_memory_documents.content
import asyncpg, asyncio
from src.shared.db_encryption import EncryptedField

async def rotate():
    old_ef = EncryptedField(OLD_KEY)
    new_ef = EncryptedField(NEW_KEY)
    pool = await asyncpg.create_pool(DATABASE_URL)
    rows = await pool.fetch("SELECT id, content FROM agent_memory_documents")
    for row in rows:
        plaintext = old_ef.decrypt(row["content"])
        new_ciphertext = new_ef.encrypt(plaintext)
        await pool.execute(
            "UPDATE agent_memory_documents SET content=$1 WHERE id=$2",
            new_ciphertext, row["id"]
        )
    await pool.close()

asyncio.run(rotate())
```

Verify after migration:

```bash
psql $DATABASE_URL -c "SELECT content FROM agent_memory_documents LIMIT 1;"
# Should return enc:v2:<base64> (or enc:v1: until prefix versioning is implemented)
```

### Step 4 — Remove the old key

1. Remove `DB_ENCRYPTION_KEY_OLD` from secrets manager
2. Update `DB_ENCRYPTION_KEY` to the new key value
3. Remove the dual-key fallback from the application code
4. Deploy the cleaned-up application

### Step 5 — Verify and document

```bash
# Confirm all rows are re-encrypted with the new key
psql $DATABASE_URL -c "SELECT COUNT(*) FROM agent_memory_documents WHERE content LIKE 'enc:v1:%';"
# Should return 0 after full rotation

# Update the rotation log
echo "$(date -u): Key rotation completed — old key ID <id>, new key ID <id>" \
  >> docs/security/key-rotation-log.md
```

---

## Emergency rotation (key exposure)

If the key was exposed, treat this as a P0 incident:

1. **Immediately** rotate the key in your secrets manager (block the old key)
2. **Assess exposure window:** determine when the exposure began and what data was at risk
3. **Follow** Steps 1–5 above with urgency
4. **Notify:** if L1/L2 PII was accessed, follow GDPR 72-hour breach notification procedure
   (`docs/runbooks/disaster-recovery.md`)
5. **Post-mortem:** conduct blameless post-mortem within 48 hours

---

## Related

- `src/shared/db_encryption.py` — `EncryptedField` implementation
- `docs/adr/ADR-0018-db-encryption-at-rest.md` — design rationale
- `.env.example` — `DB_ENCRYPTION_KEY` generation command
