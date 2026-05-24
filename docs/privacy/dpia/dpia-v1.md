# Data Protection Impact Assessment (DPIA) — v1

**GDPR Art. 35 | Version:** 1.0 | **Date:** 2026-05-24 | **Status:** Draft

---

## Section 1 — Description of Processing

| Field         | Detail                                          |
| ------------- | ----------------------------------------------- |
| Activity name | AI Agent Action Processing with LLM Integration |
| Controller    | \<Organisation Name\>                           |
| DPO           | \<DPO Name\> — dpo@\<org-domain\>               |
| Author        | \<Author Name\>                                 |
| Version       | 1.0                                             |

**Purpose:** Process user requests through AI agents that use LLM inference to reason and propose actions. Consequential actions require human approval (HITL) before execution.

**Legal basis:** Art. 6(1)(b) — contract; Art. 6(1)(f) — legitimate interest for monitoring.

**Data subjects:** Registered users submitting requests to the system.

**Data categories processed:**

| Category              | Level                 | How processed                      |
| --------------------- | --------------------- | ---------------------------------- |
| User context (masked) | L2 → masked to tokens | Sent to LLM after masking          |
| User ID               | L3                    | Included in audit log (anonymised) |
| Session metadata      | L3                    | Used for request correlation       |
| IP address            | L2 → masked           | Logged as `[IP]` token only        |

**Recipients:** Internal engineering team; LLM provider (masked data only).

**Third-country transfer:** Yes — LLM provider in \<Country\>. Mechanism: Standard Contractual Clauses (SCCs). DPA reference: DPA-\<ID\>.

**Retention:** Agent action history 90 days active + 30-day soft-delete. LLM interaction logs 30 days.

---

## Section 2 — Necessity and Proportionality

| Question                                        | Assessment                                                                                                         |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Is processing necessary for the stated purpose? | Yes — LLM inference is the core capability; no alternative achieves the same outcome without personal data context |
| Is data minimisation applied?                   | Yes — only masked context is sent to the LLM; raw PII never leaves the system boundary                             |
| Are data subject rights mechanisms in place?    | Yes — access, correction, deletion, and portability implemented; see data-processing-register.md                   |
| Is consent or another lawful basis established? | Yes — contract (Art. 6(1)(b)) for core service; documented in RoPA                                                 |

---

## Section 3 — Risk Assessment

| Risk                                                | Likelihood (1–3) | Impact (1–3) | Score | Mitigation                                                                                 | Residual Risk                      |
| --------------------------------------------------- | ---------------- | ------------ | ----- | ------------------------------------------------------------------------------------------ | ---------------------------------- |
| Unmasked PII sent to LLM provider                   | 2                | 3            | 6     | Mandatory PII filter at LLM call boundary (ADR-0012); automated test `test_pii_leakage.py` | Low — filter enforced structurally |
| Unauthorised access to audit logs                   | 2                | 3            | 6     | Role-based access control; audit logs read-only for non-Security roles                     | Low                                |
| Data subject data not deleted on request            | 1                | 3            | 3     | Deletion workflow documented and tested; 15-day SLA                                        | Low                                |
| Excessive agent autonomy — actions without approval | 1                | 3            | 3     | HITL gateway mandatory for all consequential actions; timeout = reject not approve         | Low                                |
| Third-party LLM provider data breach                | 1                | 3            | 3     | DPA confirms no training on data; SCCs in place; masked data only                          | Low                                |
| PII in log streams reaching third-party aggregator  | 2                | 2            | 4     | Logger calls `pii_filter.mask_dict()` before every write                                   | Low                                |

---

## Section 4 — Measures to Address Risks

**Technical measures:**

- PII masking at three mandatory interception points (LLM call, log write, broker publish)
- HITL gateway blocks consequential actions until human approval received
- Immutable audit log of all agent decisions
- TLS 1.3 in transit; AES-256 at rest for L1 data
- Automated monthly retention purge with verification report
- Automated PII leakage test suite (`tests/security/test_pii_leakage.py`)

**Organisational measures:**

- DPO reviews all new processing activities before production release
- Engineers complete privacy-by-design training
- Data subject rights SLA: 15 business days response
- Incident response procedure documented in `docs/runbooks/disaster-recovery.md`
- Breach notification procedure: GDPR 72-hour notification to supervisory authority

---

## Section 5 — Consultation and Approval

| Role                                        | Name         | Date              | Decision                                               |
| ------------------------------------------- | ------------ | ----------------- | ------------------------------------------------------ |
| DPO consulted                               | \<DPO Name\> | \<Date\>          | \<Approved / Approved with conditions / Not approved\> |
| DPO conditions (if any)                     |              |                   | \<Conditions\>                                         |
| Supervisory authority consultation required |              |                   | No — residual risks are low                            |
| Final approval date                         |              | \<Date\>          |                                                        |
| Next review date                            |              | \<Date + 1 year\> |                                                        |

---

## Section 6 — Version History

| Version | Date       | Author     | Changes                          |
| ------- | ---------- | ---------- | -------------------------------- |
| 1.0     | 2026-05-24 | \<Author\> | Initial DPIA for v0.1.0 scaffold |
