# Privacy Notice — Data Processing

> **Version:** 1.0 | **Last updated:** 2026-05-24
> This notice describes how this system processes personal data under LGPD (Brazil) and GDPR (EU).

---

## 1. Data Controller

**Organisation:** \<Organisation Name\>
**Address:** \<Address\>
**DPO Contact:** dpo@\<org-domain\>
**Data Protection Register:** \<Registration Number\>

---

## 2. Legal Basis for Processing

| Processing Activity   | Legal Basis (GDPR)                 | Legal Basis (LGPD)               |
| --------------------- | ---------------------------------- | -------------------------------- |
| Service provision     | Contract (Art. 6(1)(b))            | Contract execution (Art. 7, II)  |
| Security monitoring   | Legitimate interest (Art. 6(1)(f)) | Legitimate interest (Art. 7, IX) |
| Regulatory compliance | Legal obligation (Art. 6(1)(c))    | Legal obligation (Art. 7, II)    |
| AI model improvement  | Consent (Art. 6(1)(a))             | Consent (Art. 7, I)              |
| Fraud prevention      | Legitimate interest (Art. 6(1)(f)) | Legitimate interest (Art. 7, IX) |

---

## 3. Personal Data Processed

We process the following categories of personal data:

| Classification     | Examples                                    | Retention                                           |
| ------------------ | ------------------------------------------- | --------------------------------------------------- |
| **L1 — Critical**  | CPF, SSN, health data, biometric data       | Minimum necessary; encrypted at rest and in transit |
| **L2 — Sensitive** | Full name, email address, phone, IP address | Masked in logs; pseudonymised for analytics         |
| **L3 — Internal**  | Username, user ID, session token            | Internal audit logs only                            |
| **L4 — Public**    | Declared role, organisation name            | Standard retention                                  |

Full PII inventory: [`docs/privacy/pii-inventory.md`](docs/privacy/pii-inventory.md)

---

## 4. AI and LLM Processing

**Privacy-by-Design controls for AI components:**

- Personal data is **masked before ingestion** into any LLM API using `src/guardrails/pii_filter.py`
- LLM providers are contractually prohibited from using submitted data for model training (Data Processing Agreement in place)
- Agent action audit logs retain anonymised records only
- No personal data is stored in vector databases without prior pseudonymisation

---

## 5. Data Retention

| Data Type                                | Retention Period                      | Deletion Method                    |
| ---------------------------------------- | ------------------------------------- | ---------------------------------- |
| Operational logs (containing masked PII) | 30 days hot / 90 days warm            | Automated purge                    |
| Audit logs (anonymised)                  | 1 year                                | Archived then deleted              |
| Agent action history                     | 90 days active / +30 days soft delete | Automated                          |
| User account data                        | Duration of service + 30 days         | User-initiated or automated expiry |
| Backup data                              | 30 days                               | Automated rotation                 |

Full retention policy: [`docs/privacy/data-retention-policy.md`](docs/privacy/data-retention-policy.md)

---

## 6. Data Subject Rights

Under GDPR and LGPD you have the right to:

| Right                                                      | How to Exercise                       |
| ---------------------------------------------------------- | ------------------------------------- |
| **Access** your data                                       | Submit request to dpo@\<org-domain\>  |
| **Rectification** of inaccurate data                       | Submit request to dpo@\<org-domain\>  |
| **Erasure** ("right to be forgotten")                      | Submit request to dpo@\<org-domain\>  |
| **Portability** (receive your data in a structured format) | Submit request to dpo@\<org-domain\>  |
| **Object** to processing                                   | Submit request to dpo@\<org-domain\>  |
| **Restrict** processing                                    | Submit request to dpo@\<org-domain\>  |
| **Withdraw consent** at any time                           | Via account settings or email to dpo@ |

Response time: **15 business days** (extendable to 30 with notice).

---

## 7. Third-Party Processors

| Processor               | Purpose                | Country     | DPA Reference |
| ----------------------- | ---------------------- | ----------- | ------------- |
| \<LLM Provider\>        | AI inference           | \<Country\> | DPA-\<ID\>    |
| \<Cloud Provider\>      | Infrastructure hosting | \<Country\> | DPA-\<ID\>    |
| \<Monitoring Provider\> | Observability          | \<Country\> | DPA-\<ID\>    |

All third-party processors operate under a signed Data Processing Agreement (DPA).

---

## 8. Cross-Border Transfers

Data transfers outside Brazil or the EU/EEA are made under:

- **GDPR:** Standard Contractual Clauses (SCCs) or adequacy decision
- **LGPD:** Equivalent protections as required by ANPD

---

## 9. Security Measures

- Encryption at rest (AES-256) and in transit (TLS 1.3)
- PII masking before all LLM calls, log writes, and event publishing
- Role-based access control with least-privilege principle
- Immutable audit log of all agent actions
- Regular penetration testing and DAST scans
- SBOM generated and signed for every release

---

## 10. Data Protection Impact Assessment

A DPIA (GDPR Art. 35) and RIPD (LGPD Art. 38) are completed before every production release that introduces or changes personal data processing.

- DPIA: [`docs/privacy/dpia/dpia-v1.md`](docs/privacy/dpia/dpia-v1.md)
- RIPD: [`docs/privacy/ripd/ripd-v1.md`](docs/privacy/ripd/ripd-v1.md)

---

## 11. Breach Notification

In the event of a personal data breach:

- **GDPR:** Notification to supervisory authority within 72 hours; affected individuals notified without undue delay where high risk
- **LGPD:** Notification to ANPD and affected data subjects within a reasonable timeframe

To report a suspected breach: security@\<org-domain\>

---

## 12. Changes to This Notice

We will notify data subjects of material changes to this notice via email or in-app notification at least 30 days before changes take effect.

---

_This notice is governed by the laws of Brazil (LGPD) and the European Union (GDPR). For complaints, you may contact the relevant supervisory authority: ANPD (Brazil) or your local EU data protection authority._
