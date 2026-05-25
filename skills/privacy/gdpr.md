# Skill — GDPR Compliance

**Owner:** DPO | **Reviewer:** Legal | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill when working with EU data subjects or any GDPR obligations.

---

## Key Obligations

| Obligation                      | Article      | Requirement                                                                    |
| ------------------------------- | ------------ | ------------------------------------------------------------------------------ |
| Lawful basis                    | Art. 6       | Every processing activity must have a documented legal basis                   |
| Special categories              | Art. 9       | Health, biometric, racial data requires explicit consent or specific exemption |
| Data subject rights             | Arts. 15–22  | Access, rectification, erasure, restriction, portability, objection            |
| DPIA                            | Art. 35      | Required before high-risk processing                                           |
| Breach notification (authority) | Art. 33      | Notify supervisory authority within 72 hours                                   |
| Breach notification (subjects)  | Art. 34      | Notify data subjects without undue delay if high risk                          |
| Cross-border transfers          | Chapter V    | Transfers outside EEA require adequate safeguards                              |
| Data minimisation               | Art. 5(1)(c) | Collect only what is necessary for the stated purpose                          |
| Retention limits                | Art. 5(1)(e) | Keep no longer than necessary                                                  |

---

## Determining Lawful Basis (Art. 6)

| Basis                               | When applicable                                             |
| ----------------------------------- | ----------------------------------------------------------- |
| Consent (Art. 6(1)(a))              | Freely given, specific, informed, unambiguous; withdrawable |
| Contract (Art. 6(1)(b))             | Necessary to perform a contract with the data subject       |
| Legal obligation (Art. 6(1)(c))     | Required by EU or member state law                          |
| Vital interests (Art. 6(1)(d))      | Protect life                                                |
| Legitimate interests (Art. 6(1)(f)) | Proportionate; balancing test documented                    |

For **special category data** (Art. 9): explicit consent or a specific Art. 9(2) exemption required.

---

## When Is a DPIA Required?

High-risk processing criteria (Art. 35(3)):

- Systematic and extensive profiling with significant effects on individuals
- Large-scale processing of special category data
- Systematic monitoring of publicly accessible areas
- Automated decision-making with significant effects (including AI agents)

This system processes data through an AI agent with automated decision-making — **DPIA is required**.

Template: `docs/privacy/dpia/dpia-v1.md`
Submit to DPO at least **5 business days** before production.

---

## How to Complete the DPIA

Required sections (Art. 35(7)):

1. Systematic description of processing operations and purposes
2. Necessity and proportionality assessment
3. Risk assessment (likelihood × severity for each identified risk)
4. Measures to address risks (technical + organisational)
5. DPO consultation record
6. Approval signature (DPO; supervisory authority if residual risk remains high)

---

## Data Subject Rights (Arts. 15–22)

| Right                   | Deadline            | Notes                                                          |
| ----------------------- | ------------------- | -------------------------------------------------------------- |
| Access (Art. 15)        | 1 month             | Extend to 3 months for complex requests; notify within 1 month |
| Rectification (Art. 16) | 1 month             | Correct inaccurate or incomplete data                          |
| Erasure (Art. 17)       | 1 month             | "Right to be forgotten"; exceptions for legal claims           |
| Restriction (Art. 18)   | Without undue delay | Pause processing while accuracy or lawfulness is contested     |
| Portability (Art. 20)   | 1 month             | Machine-readable format (JSON/CSV)                             |
| Objection (Art. 21)     | Without undue delay | Must stop processing unless compelling legitimate grounds      |

---

## Cross-Border Transfer Mechanisms (Chapter V)

| Mechanism                                    | When to use                                                   |
| -------------------------------------------- | ------------------------------------------------------------- |
| Adequacy decision (Art. 45)                  | Transfer to country with EU adequacy decision                 |
| Standard contractual clauses (Art. 46(2)(c)) | Transfer to other countries; SCCs signed with processor       |
| Binding corporate rules (Art. 47)            | Intra-group transfers; BCRs approved by supervisory authority |
| Explicit consent (Art. 49(1)(a))             | One-off transfers with informed, explicit consent             |

Current LLM API transfers: governed by SCCs — see `docs/privacy/data-processing-register.md`.

---

## 72-Hour Breach Notification Checklist (Art. 33)

When a personal data breach is detected:

- [ ] Hour 0: Contain breach; notify DPO immediately
- [ ] Hour 4: DPO assesses whether notification to supervisory authority required
- [ ] Hour 24: Draft notification if required (what, when, who affected, consequences, measures)
- [ ] Hour 72: Submit formal notification to supervisory authority (HARD DEADLINE)
- [ ] If high risk to individuals (Art. 34): notify affected data subjects without undue delay
- [ ] Document breach in internal register regardless of notification decision

The 72-hour clock starts at the moment the organisation becomes **aware** of the breach, not when it occurred.
