# ADR-0018 — Database Encryption at Rest

**Status:** Accepted
**Date:** 2026-05-28
**Authors:** Security Lead, DPO
**Spec:** `specs/privacy/db-encryption-at-rest.md`

---

## Context

The DPIA (§4.2) and RIPD both require AES-256 at-rest encryption for L1 and L2 PII
stored in PostgreSQL. An audit conducted on 2026-05-28 found this requirement was
stated in policy but not implemented:

- `agent_memory_documents.content` — stores masked context that may contain L2 PII
  residuals; currently plaintext
- `audit_events.metadata` — stores action parameters that may contain L2 identifiers;
  currently plaintext

The gap creates a compliance violation under LGPD Art. 46 and GDPR Art. 32, both of
which require appropriate technical measures to protect personal data at rest.

---

## Decision

Implement **application-layer AES-256-GCM field encryption** for affected columns.

### Why application-layer (not pgcrypto or full-disk)?

| Approach                       | Protects against compromised DB user? | Key stays outside DB?  | Query performance | Key rotation                     |
| ------------------------------ | ------------------------------------- | ---------------------- | ----------------- | -------------------------------- |
| Full-disk encryption           | No                                    | No                     | Transparent       | OS-level                         |
| pgcrypto (DB-side functions)   | No — DB executes decrypt              | No                     | Moderate          | Schema change needed             |
| **Application-layer (chosen)** | **Yes**                               | **Yes — key in Vault** | Minimal overhead  | Zero-downtime via version prefix |

Full-disk encryption protects against physical media theft but not against a
compromised database user — an attacker with `SELECT` on the table reads plaintext.

pgcrypto decrypts inside the database process, meaning the key must be sent to the
DB on every decrypt call and is visible in the DB process memory.

Application-layer encryption means the key never leaves the application pod. A
compromised DB user reads only ciphertext. The Vault-managed key is the only path
to the plaintext.

### Algorithm

**AES-256-GCM** — authenticated encryption providing both confidentiality and integrity.
96-bit random nonce per call (IND-CPA secure — same plaintext produces different
ciphertext on every call). 128-bit authentication tag detects tampering before decryption.

### Wire format

```
enc:v1:<base64(nonce[12] || ciphertext_with_tag)>
```

The `v1` version identifier enables key rotation without schema changes or downtime.

### Key management

Keys stored in HashiCorp Vault (ADR-0008). Injected at pod startup via Vault Agent
Sidecar as `DB_ENCRYPTION_KEY` (64-char hex / 32 bytes). Never written to disk or logs.
Rotation schedule: 180 days, same cadence as `SECRET_KEY` per ADR-0008.

### pgcrypto extension

Still enabled (migration 0002) for future use cases requiring DB-side cryptographic
functions (e.g., `gen_random_uuid()`, `digest()` for integrity checks in migrations).

---

## Consequences

### Positive

- LGPD Art. 46 and GDPR Art. 32 compliance achieved for at-rest encryption
- Key never sent to the database — a compromised DB user reads only ciphertext
- Zero-downtime key rotation via the `enc:vN:` version prefix
- `decrypt()` plaintext passthrough enables rolling deployments over existing data
- Audit tag authentication detects row-level tampering

### Negative / Trade-offs

- Encrypted columns cannot be searched or indexed by the DB engine (content is
  opaque ciphertext). For `agent_memory_documents`, the embedding vector is used
  for similarity search — the content field is only read after retrieval, so this
  is not a functional constraint.
- `cryptography` package added as a direct dependency (it is already a transitive
  dependency via other packages; making it explicit has no version-conflict risk).
- Local development without Vault requires generating a dummy `DB_ENCRYPTION_KEY`
  in `.env`. The `.env.example` provides generation instructions.

---

## Alternatives Considered

**pgcrypto `pgp_sym_encrypt` / `pgp_sym_decrypt`**
Rejected: decryption key passed to every SQL call — visible in PostgreSQL process
memory and potentially in query logs if `log_min_duration_statement` is enabled.
Does not meet the requirement that the key never reach the DB process.

**Full-disk encryption (LUKS, cloud provider block-level)**
Rejected: protects only against physical media theft and decommissioned storage.
Does not protect against a compromised DB user or a misconfigured network policy
that allows direct DB access. Insufficient for LGPD/GDPR column-level requirements.

**PostgreSQL Transparent Data Encryption (TDE) via pg_tde extension**
Considered: encrypts at the storage layer within PostgreSQL; supports key from
an external KMS. Rejected for now because pg_tde is not GA in PostgreSQL 16 and
introduces an additional dependency on a less-mature extension. Revisit in 12 months.

**HashiCorp Vault Transit Secrets Engine**
Considered: offloads all encrypt/decrypt operations to Vault, eliminating in-process
key handling. Rejected for initial implementation due to network latency on every
DB write/read (agent memory operations are frequent). Retain as a future upgrade path
if compliance requirements demand HSM-backed key operations.
