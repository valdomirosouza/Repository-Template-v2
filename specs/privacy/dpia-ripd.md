# DPIA / RIPD Spec

**Status:** Approved | **Owner:** DPO | **Last updated:** 2026-05-24
**ADR references:** ADR-0012 (PII Masking), ADR-0013 (Data Retention)

---

## Purpose

This spec defines the process and minimum content requirements for:

- **DPIA** — Data Protection Impact Assessment (GDPR Art. 35)
- **RIPD** — Relatório de Impacto à Proteção de Dados (LGPD Art. 38)

Both assessments are **mandatory before** any processing of personal data begins in production. No feature that introduces new personal data processing may be deployed without a completed and DPO-approved DPIA/RIPD.

---

## When a DPIA/RIPD Is Required

A new or updated DPIA/RIPD is required when any of the following occur:

| Trigger                                  | Reassessment scope       |
| ---------------------------------------- | ------------------------ |
| New personal data category introduced    | Full new assessment      |
| New third-party processor added          | Processor addendum       |
| Processing purpose changes               | Full reassessment        |
| New cross-border data transfer           | Transfer impact section  |
| Material change to retention period      | Retention section update |
| New automated decision-making introduced | AI/ADM section update    |
| Annual review cycle                      | Full review              |

---

## Document Location

```
docs/privacy/dpia/dpia-v<N>.md      — GDPR assessment (English)
docs/privacy/ripd/ripd-v<N>.md      — LGPD assessment (Portuguese)
```

Version increments on every material change. Both documents must be updated together — they cover the same processing activities under different regulatory frameworks.

---

## Required Sections — DPIA (GDPR Art. 35)

### 1. Processing Activity Description

- Name and purpose of processing
- Categories of personal data
- Data subjects affected (types and estimated volume)
- Recipients and processors
- Cross-border transfers (if any)

### 2. Necessity and Proportionality Assessment

- Legal basis (GDPR Art. 6 / Art. 9)
- Minimum data principle: why each field is necessary
- Retention justification: why retention period is the minimum required

### 3. Risk Identification

For each identified risk:

- Risk description
- Likelihood (Low / Medium / High)
- Severity (Low / Medium / High)
- Risk level = Likelihood × Severity

Minimum risks to assess:

- Unauthorised access to personal data
- Unintended disclosure via LLM processing
- Excessive retention beyond stated period
- Inaccurate automated decision affecting data subject
- Failure of erasure request fulfillment

### 4. Mitigation Measures

For each identified risk:

- Technical measure (e.g., encryption, masking, access control)
- Organisational measure (e.g., training, policy, HITL oversight)
- Residual risk after mitigation
- Acceptance criteria: residual risk must be Low for processing to proceed

### 5. Consultation

- Internal DPO review and approval (required)
- Data subject representative consultation (if high residual risk)
- Supervisory authority prior consultation (if residual risk remains high after mitigation)

### 6. Approval and Review

- DPO approval signature and date
- Next review date (maximum: 1 year from approval)
- Change history

---

## Required Sections — RIPD (LGPD Art. 38)

Mirrors DPIA structure with the following LGPD-specific additions:

### Brazilian Law Mapping

- Legal basis under LGPD Art. 7 (or Art. 11 for sensitive data)
- Legitimate interest balancing test (if Art. 7(IX) is the basis)
- ANPD notification obligations (if applicable)

### Data Subject Rights (LGPD Art. 18)

- Access: how data subjects can request a copy
- Correction: how inaccurate data is corrected
- Anonymisation or deletion: process and timeline (15 days)
- Portability: format and delivery method
- Revocation of consent: mechanism and effect

### International Transfer (LGPD Art. 33)

- Transfer mechanism (adequacy decision, standard clauses, or consent)
- Countries/regions data is transferred to
- Safeguards in place

---

## Approval Gate

No personal data processing feature is deployed to staging or production until:

- [ ] DPIA approved by DPO (signature on document)
- [ ] RIPD approved by DPO (signature on document)
- [ ] PRR checklist item `PRR-PRIV-001` marked complete
- [ ] PR description references both documents

---

## Current Approved Assessments

| Version | Scope                     | DPO approved | Review due |
| ------- | ------------------------- | ------------ | ---------- |
| v1      | Initial system processing | 2026-05-24   | 2027-05-24 |

Full documents:

- `docs/privacy/dpia/dpia-v1.md`
- `docs/privacy/ripd/ripd-v1.md`
