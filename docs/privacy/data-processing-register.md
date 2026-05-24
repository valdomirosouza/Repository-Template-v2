# Data Processing Register (RoPA)

**Record of Processing Activities — GDPR Art. 30 / LGPD Art. 37**
**Controller:** \<Organisation Name\>
**DPO:** dpo@\<org-domain\>
**Last updated:** 2026-05-24

---

## Controller Details

| Field                           | Value                   |
| ------------------------------- | ----------------------- |
| Organisation name               | \<Organisation Name\>   |
| Address                         | \<Address\>             |
| DPO name                        | \<DPO Name\>            |
| DPO contact                     | dpo@\<org-domain\>      |
| Data protection register number | \<Registration Number\> |

---

## Processing Activities

### Activity 1 — User Authentication and Session Management

| Field                      | Detail                                                  |
| -------------------------- | ------------------------------------------------------- |
| **Purpose**                | Authenticate users and maintain secure sessions         |
| **Legal basis (GDPR)**     | Contract — Art. 6(1)(b)                                 |
| **Legal basis (LGPD)**     | Contract execution — Art. 7, II                         |
| **Data categories**        | L2: email, username; L3: session token, user ID         |
| **Data subjects**          | Registered users                                        |
| **Recipients**             | Internal auth service only                              |
| **Third-party processors** | Cloud provider (infrastructure hosting)                 |
| **Cross-border transfer**  | No                                                      |
| **Retention**              | Session duration + 30 days post-closure                 |
| **Technical measures**     | TLS 1.3, bcrypt password hashing, JWT with short expiry |
| **DPIA required**          | No                                                      |

---

### Activity 2 — AI Agent Action Processing

| Field                      | Detail                                                                                    |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| **Purpose**                | Process user requests via AI agents; route consequential actions through HITL approval    |
| **Legal basis (GDPR)**     | Contract — Art. 6(1)(b); Legitimate interest — Art. 6(1)(f)                               |
| **Legal basis (LGPD)**     | Contract execution — Art. 7, II; Legitimate interest — Art. 7, IX                         |
| **Data categories**        | L2: masked user context; L3: user ID, correlation IDs                                     |
| **Data subjects**          | Registered users submitting requests                                                      |
| **Recipients**             | LLM provider (masked data only — no L1/L2 sent unmasked)                                  |
| **Third-party processors** | LLM provider (DPA in place; no training on submitted data)                                |
| **Cross-border transfer**  | Yes — SCCs / adequacy decision in place                                                   |
| **Retention**              | Agent action history: 90 days + 30-day soft-delete                                        |
| **Technical measures**     | PII masking before LLM call, HITL approval for consequential actions, immutable audit log |
| **DPIA required**          | Yes — see `docs/privacy/dpia/dpia-v1.md`                                                  |

---

### Activity 3 — Observability and Log Collection

| Field                      | Detail                                                                   |
| -------------------------- | ------------------------------------------------------------------------ |
| **Purpose**                | Monitor system health, debug incidents, support SLO compliance           |
| **Legal basis (GDPR)**     | Legitimate interest — Art. 6(1)(f)                                       |
| **Legal basis (LGPD)**     | Legitimate interest — Art. 7, IX                                         |
| **Data categories**        | L2 (masked as tokens): `[IP]`, `[EMAIL]` in log context; L3: `[USER_ID]` |
| **Data subjects**          | All users whose requests generate log records                            |
| **Recipients**             | Internal SRE team; log aggregator (third-party)                          |
| **Third-party processors** | Log aggregation provider (DPA in place)                                  |
| **Cross-border transfer**  | Depends on provider — document in DPA reference                          |
| **Retention**              | 30 days hot / 90 days warm — automated purge                             |
| **Technical measures**     | PII masking before log write, structured JSON, OTel trace correlation    |
| **DPIA required**          | No — masked data only                                                    |

---

### Activity 4 — Analytics and Reporting

| Field                      | Detail                                                     |
| -------------------------- | ---------------------------------------------------------- |
| **Purpose**                | Understand usage patterns, improve system performance      |
| **Legal basis (GDPR)**     | Legitimate interest — Art. 6(1)(f)                         |
| **Legal basis (LGPD)**     | Legitimate interest — Art. 7, IX                           |
| **Data categories**        | L3/L4 only: pseudonymised user IDs, aggregated counts      |
| **Data subjects**          | All users                                                  |
| **Recipients**             | Internal product and engineering teams                     |
| **Third-party processors** | Analytics platform (DPA in place)                          |
| **Cross-border transfer**  | Depends on provider                                        |
| **Retention**              | Per analytics platform retention config                    |
| **Technical measures**     | Pseudonymisation before analytics ingestion, no L1/L2 data |
| **DPIA required**          | No                                                         |

---

### Activity 5 — Third-Party LLM API Calls

| Field                      | Detail                                                                         |
| -------------------------- | ------------------------------------------------------------------------------ |
| **Purpose**                | Generate AI responses and classifications as part of agent processing          |
| **Legal basis (GDPR)**     | Contract — Art. 6(1)(b)                                                        |
| **Legal basis (LGPD)**     | Contract execution — Art. 7, II                                                |
| **Data categories**        | Masked context only — L1/L2 replaced with tokens before submission             |
| **Data subjects**          | Users whose requests are processed by agents                                   |
| **Recipients**             | LLM provider                                                                   |
| **Third-party processors** | \<LLM Provider Name\> (DPA-\<ID\>: confirms no training on submitted data)     |
| **Cross-border transfer**  | Yes — \<Country\> — SCCs in place                                              |
| **Retention**              | Provider retains for \<N\> days per DPA; we retain anonymised logs for 30 days |
| **Technical measures**     | PII masking mandatory before every API call (ADR-0012)                         |
| **DPIA required**          | Yes — see `docs/privacy/dpia/dpia-v1.md`                                       |

---

## Maintenance

This register must be updated **before** any production release that:

- Introduces a new processing activity
- Changes the purpose, data categories, or recipients of an existing activity
- Adds a new third-party processor

The DPO signs off on every update to this register.
