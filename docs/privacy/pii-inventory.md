# PII Inventory — Fields Catalogue & Classification

**Owner:** DPO
**Last reviewed:** 2026-05-24
**Review cadence:** Before every PR that introduces a new personal data field.

---

## Classification Scheme

| Level  | Name      | Description                                                                                                      | Masking rule                                                                                                                                               |
| ------ | --------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **L1** | Critical  | Data that can directly cause harm if exposed: national IDs, health/medical, biometric, financial account numbers | Encrypt at rest (AES-256) and in transit (TLS 1.3). **Never** in logs. **Never** sent to LLM unmasked. Token: `[CPF]`, `[HEALTH]`, `[BIOMETRIC]`, `[CARD]` |
| **L2** | Sensitive | Data that identifies a person: full name, email, phone, IP address, physical address, date of birth              | Mask in all log streams. Pseudonymise for analytics. Token: `[NAME]`, `[EMAIL]`, `[PHONE]`, `[IP]`, `[ADDRESS]`, `[DOB]`                                   |
| **L3** | Internal  | Identifiers used internally: username, user ID, session token, device ID, correlation IDs                        | Allowed in internal audit logs. Masked in external/third-party log streams. Token: `[USER_ID]`, `[TOKEN]`, `[SESSION]`                                     |
| **L4** | Public    | Data the person has publicly disclosed: declared job title, public organisation name, public profile URL         | No special handling required.                                                                                                                              |

---

## Masking Token Format

Replacement tokens follow the pattern `[FIELD_TYPE]`. They preserve semantic structure
(a reader can tell what kind of data was present) without exposing the value.

| Token         | Field type                    | Level |
| ------------- | ----------------------------- | ----- |
| `[CPF]`       | Brazilian national ID (CPF)   | L1    |
| `[SSN]`       | US Social Security Number     | L1    |
| `[HEALTH]`    | Health or medical record data | L1    |
| `[BIOMETRIC]` | Biometric data                | L1    |
| `[CARD]`      | Payment card number           | L1    |
| `[EMAIL]`     | Email address                 | L2    |
| `[NAME]`      | Full or partial name          | L2    |
| `[PHONE]`     | Phone number (any format)     | L2    |
| `[IP]`        | IPv4 or IPv6 address          | L2    |
| `[ADDRESS]`   | Physical address              | L2    |
| `[DOB]`       | Date of birth                 | L2    |
| `[USER_ID]`   | Internal user identifier      | L3    |
| `[TOKEN]`     | Session or API token          | L3    |
| `[SESSION]`   | Session ID                    | L3    |
| `[UUID]`      | UUID (when tied to a person)  | L3    |

---

## Field Inventory

| Field Name              | Level | Example (synthetic)          | Source System   | Masking Token | Retention                |
| ----------------------- | ----- | ---------------------------- | --------------- | ------------- | ------------------------ |
| `user.cpf`              | L1    | `000.000.000-00`             | User service    | `[CPF]`       | Per user account policy  |
| `user.health_data`      | L1    | `{"condition": "SYNTHETIC"}` | Health module   | `[HEALTH]`    | Per product requirement  |
| `payment.card_number`   | L1    | `0000-0000-0000-0000`        | Payment service | `[CARD]`      | 30 days post-transaction |
| `user.email`            | L2    | `fake@example.com`           | Auth service    | `[EMAIL]`     | Active + 30 days         |
| `user.full_name`        | L2    | `Test User`                  | User service    | `[NAME]`      | Active + 30 days         |
| `user.phone`            | L2    | `+00 00 00000-0000`          | User service    | `[PHONE]`     | Active + 30 days         |
| `request.ip_address`    | L2    | `192.0.2.1`                  | API gateway     | `[IP]`        | 30 days (log retention)  |
| `user.date_of_birth`    | L2    | `0000-00-00`                 | User service    | `[DOB]`       | Active + 30 days         |
| `user.physical_address` | L2    | `123 Test Street`            | User service    | `[ADDRESS]`   | Active + 30 days         |
| `session.token`         | L3    | `SYNTHETIC_TOKEN_VALUE`      | Auth service    | `[TOKEN]`     | Session duration         |
| `user.id`               | L3    | `usr_00000000`               | All services    | `[USER_ID]`   | Active + 30 days         |
| `user.username`         | L3    | `testuser`                   | Auth service    | `[USER_ID]`   | Active + 30 days         |
| `user.role`             | L4    | `analyst`                    | Auth service    | None          | Active + 30 days         |
| `org.name`              | L4    | `Example Corp`               | Org service     | None          | Active duration          |

---

## Mandatory Interception Points

Per ADR-0012, PII masking is applied at three fixed boundaries:

1. **Before every LLM API call** — `src/guardrails/pii_filter.py` called by LLM client wrapper
2. **Before every log write** — `src/observability/logger.py` calls `pii_filter.mask_dict()`
3. **Before every broker event publish** — Kafka producer calls `pii_filter.mask_dict()`

No personal data may pass these boundaries unmasked.

---

## Synthetic Data Standard for Tests

All test fixtures and test data must use clearly synthetic values:

| Field type | Synthetic standard                             |
| ---------- | ---------------------------------------------- |
| Email      | `fake@example.com`, `test@test.org`            |
| CPF        | `000.000.000-00` (all zeros — not a valid CPF) |
| IP address | `192.0.2.x` (TEST-NET per RFC 5737)            |
| Phone      | `+00 00 00000-0000`                            |
| Name       | `Test User`, `Synthetic Person`                |
| Card       | `0000-0000-0000-0000`                          |

---

## Pre-Release Checklist

Before merging any PR that introduces a new personal data field:

- [ ] Field added to the inventory table above with correct level, token, and retention
- [ ] Masking rule implemented in `src/guardrails/pii_filter.py`
- [ ] Unit test added to `tests/unit/guardrails/test_pii_filter.py` using synthetic data
- [ ] DPO notified for any new L1 or L2 field
- [ ] DPIA/RIPD reviewed if this field changes the processing activity scope
