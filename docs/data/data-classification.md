# Data Classification

> **Owner:** DPO (with Tech Lead) | **Status:** Living reference
> This page is a **navigational summary**. The authoritative L1–L4 scheme and per-field inventory
> live in `specs/privacy/pii-inventory.md` — that file wins on any discrepancy. Do not redefine the
> levels here; update the inventory and link it.

The classification drives three enforced behaviours: **masking** before logs/LLM/broker
(`src/guardrails/pii_filter.py`), **encryption at rest** for L1/L2 (`src/shared/db_encryption.py`,
ADR-0018/0019), and **retention** caps (`specs/privacy/data-retention.md`).

---

## Levels (summary — authoritative source: `specs/privacy/pii-inventory.md`)

| Level  | Name      | Meaning                                  | Example masking tokens       | Retention cap |
| ------ | --------- | ---------------------------------------- | ---------------------------- | ------------- |
| **L1** | Critical  | Directly identifies a person; regulated  | `[CPF]`, `[CARD]`            | 90 days       |
| **L2** | Sensitive | Identifies in combination; moderate risk | `[EMAIL]`, `[PHONE]`, `[IP]` | 1 year        |
| **L3** | Internal  | Technical identifiers; low direct risk   | `[TOKEN]`, `[UUID]`          | 2 years       |
| **L4** | Public    | Publicly available; no masking required  | pass through                 | per policy    |

Representative fields (see the inventory for the complete list):

- **L1:** `cpf`, `national_id`, `health_record`, `biometric_data`, `financial_account`
- **L2:** `email`, `full_name`, `phone_number`, `ip_address`, `home_address`, `date_of_birth`
- **L3:** `user_id`, `session_token`, `request_id`, `agent_id`

---

## Handling rules by level

| Requirement                                    | L1  | L2  | L3        | L4  |
| ---------------------------------------------- | --- | --- | --------- | --- |
| Mask before log / LLM call / broker publish    | ✓   | ✓   | ✓\*       | —   |
| Encrypt at rest (AES-256-GCM `EncryptedField`) | ✓   | ✓   | —         | —   |
| TLS in transit (`rediss://` Redis in prod)     | ✓   | ✓   | ✓         | ✓   |
| Allowed in error `detail` / API response       | —   | —   | id-only   | ✓   |
| DPIA/RIPD review on new processing             | ✓   | ✓   | as needed | —   |

\* L3 identifiers are masked in narrative/log context but may appear as resource ids in URLs and
audit records (e.g. `request_id`), which is why audit storage is access-controlled and append-only.

## Where each backend sits

| Backend                 | Classification handling                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------- |
| PostgreSQL              | L1/L2 columns via `EncryptedField`; audit/HITL tables append-only (UPDATE/DELETE revoked) |
| Redis                   | HITL payloads encrypted before write; `rediss://` + TLS in prod (ADR-0019)                |
| Kafka                   | PII masked **before** publish; envelopes carry `trace_id`, never raw PII                  |
| Vector store            | embeds masked content; `content` column encrypted (migration 0003)                        |
| Logs / metrics / traces | masked; never carry L1/L2 (CLAUDE.md §3.1, OWASP A09)                                     |

---

## Related

- `specs/privacy/pii-inventory.md` — **authoritative** L1–L4 definitions & field inventory
- `specs/privacy/data-retention.md` · `docs/privacy/data-retention-policy.md` — retention enforcement
- `docs/privacy/data-processing-register.md` — processing activities
- `docs/data/data-model-catalog.md` — entities and which fields are classified/encrypted
- ADR-0012 (PII masking), ADR-0018 (DB encryption), ADR-0019 (Redis TLS/encryption)
