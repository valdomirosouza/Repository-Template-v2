# PII Inventory Spec

**Status:** Approved | **Owner:** DPO | **Last updated:** 2026-05-24
**ADR references:** ADR-0012 (PII Masking Strategy), ADR-0013 (Data Retention)

---

## Classification Scheme

| Level | Name      | Description                                     | Masking tokens               | Retention cap |
| ----- | --------- | ----------------------------------------------- | ---------------------------- | ------------- |
| L1    | Critical  | Directly identifies a natural person; regulated | `[CPF]`, `[CARD]`            | 90 days       |
| L2    | Sensitive | Identifies with combination; moderate risk      | `[EMAIL]`, `[PHONE]`, `[IP]` | 1 year        |
| L3    | Internal  | Technical identifiers; low direct risk          | `[TOKEN]`, `[UUID]`          | 2 years       |
| L4    | Public    | Publicly available; no masking required         | Pass through                 | Per policy    |

---

## Field Inventory

### L1 — Critical PII

| Field name          | Format                      | System(s) present       | Legal basis (LGPD/GDPR)       |
| ------------------- | --------------------------- | ----------------------- | ----------------------------- |
| `cpf`               | `\d{3}\.\d{3}\.\d{3}-\d{2}` | API Gateway, DB         | Art. 7(V) LGPD — consent      |
| `national_id`       | Country-specific            | API Gateway, DB         | Art. 7(V) LGPD — consent      |
| `health_record`     | Free text / coded           | Agent context only      | Art. 11 LGPD — sensitive data |
| `biometric_data`    | Binary / encoded            | Not currently processed | —                             |
| `financial_account` | Masked card/account         | API Gateway             | Art. 7(V) LGPD — contract     |

### L2 — Sensitive PII

| Field name      | Format                 | System(s) present         | Legal basis                      |
| --------------- | ---------------------- | ------------------------- | -------------------------------- |
| `email`         | RFC 5321               | API Gateway, DB, Notifier | Art. 7(V) — consent              |
| `full_name`     | Free text              | API Gateway, DB           | Art. 7(V) — consent              |
| `phone_number`  | E.164                  | API Gateway, DB           | Art. 7(V) — consent              |
| `ip_address`    | IPv4/IPv6              | API Gateway logs          | Art. 7(IX) — legitimate interest |
| `home_address`  | Free text / structured | API Gateway, DB           | Art. 7(V) — consent              |
| `date_of_birth` | ISO 8601               | DB only                   | Art. 7(V) — consent              |

### L3 — Internal Identifiers

| Field name      | Format        | System(s) present    |
| --------------- | ------------- | -------------------- |
| `user_id`       | UUID          | All services         |
| `session_token` | Opaque string | API Gateway, Redis   |
| `request_id`    | UUID          | All services         |
| `agent_id`      | String        | Agent Service, Audit |

---

## Masking Implementation Requirements

### Detection

Field-level masking is applied by field **name** mapping first, then structural format validation as a secondary check. Detection logic:

- Uses field name registry (maintained in `src/guardrails/pii_filter.py`)
- Applies format validation for fields that may appear under varied names (e.g., CPF-formatted strings)
- Never stores, logs, or forwards matched values — only replacement tokens

### Synthetic Data Standard

All test fixtures and development seeds **must** use:

| PII type   | Synthetic placeholder                  |
| ---------- | -------------------------------------- |
| CPF        | `000.000.000-00`                       |
| Email      | `test@example.com`                     |
| Name       | `Test User`                            |
| IP address | `192.0.2.1` (RFC 5737 TEST-NET)        |
| Phone      | `+55 11 00000-0000`                    |
| User ID    | `00000000-0000-0000-0000-000000000000` |

Real PII in test files, fixtures, or seed data is a P1 security incident.

---

## Pre-Release PII Checklist

Before any release to staging or production, the responsible engineer must verify:

- [ ] No real PII in test fixtures (`tests/`, `harness/`, `seeds/`)
- [ ] No real PII in example files (`.env.example`, `docs/`)
- [ ] `pii_filter` unit tests pass with 100% branch coverage
- [ ] `test_pii_leakage.py` security test passes with zero leakage findings
- [ ] Log aggregator sampling verified: no L1/L2 fields in emitted logs
- [ ] Kafka consumer trace verified: no L1/L2 fields in published events

---

## Masking Verification

Quarterly automated verification:

1. Run `make test-security` — includes PII leakage scanner across all outputs
2. Sample 100 audit log entries — confirm L1/L2 fields are masked
3. Sample 100 Kafka events — confirm L1/L2 fields are masked
4. Document results in `docs/postmortems/YYYY-MM-DD-pii-verification.md`
