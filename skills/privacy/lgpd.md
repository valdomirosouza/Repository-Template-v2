# Skill — LGPD Compliance

**Owner:** DPO | **Reviewer:** Legal | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill when working with Brazilian data subjects or any LGPD obligations.

---

## Key Obligations

| Obligation          | Article | Requirement                                                                      |
| ------------------- | ------- | -------------------------------------------------------------------------------- |
| Lawful basis        | Art. 7  | Every processing activity must have a documented legal basis                     |
| Sensitive data      | Art. 11 | Health, biometric, racial data requires explicit consent or other specific basis |
| Data subject rights | Art. 18 | Access, correction, anonymisation, deletion, portability, revocation             |
| DPO designation     | Art. 41 | DPO must be designated and publicly identified                                   |
| RIPD                | Art. 38 | Required before processing that may pose risks to data subjects                  |
| Breach notification | Art. 48 | Notify ANPD and affected data subjects of significant breaches                   |
| Retention limits    | Art. 16 | Data must be deleted when no longer necessary for the stated purpose             |

---

## Determining Lawful Basis (Art. 7)

Choose the most appropriate basis and document it in the processing register:

| Basis                            | When applicable                                                 |
| -------------------------------- | --------------------------------------------------------------- |
| Consent (Art. 7(I))              | User explicitly opted in; revocable at any time                 |
| Contract (Art. 7(V))             | Processing necessary to fulfil a contract with the data subject |
| Legal obligation (Art. 7(II))    | Processing required by law                                      |
| Legitimate interest (Art. 7(IX)) | Proportionate benefit; balancing test required                  |
| Vital interests (Art. 7(III))    | Protection of life or safety                                    |

For **sensitive data** (Art. 11): only explicit consent or specific legal authorisation applies.

---

## When Is a RIPD Required?

A RIPD (Relatório de Impacto à Proteção de Dados Pessoais) is required when processing:

- May pose risks to the freedom and fundamental rights of data subjects
- Involves automated decision-making affecting data subjects
- Uses sensitive personal data (Art. 11)
- Involves data subjects who are children or adolescents
- Is a new or materially changed processing activity

When in doubt: consult the DPO. Filing a RIPD when not strictly required is always acceptable.

---

## How to Complete the RIPD

Template: `docs/privacy/ripd/ripd-v1.md` (in Portuguese, as required)

Required sections:

1. Descrição do tratamento (processing description)
2. Base legal e finalidade (legal basis and purpose)
3. Necessidade e proporcionalidade (necessity and proportionality)
4. Identificação de riscos (risk identification — likelihood × severity)
5. Medidas de mitigação (technical and organisational measures)
6. Aprovação do Encarregado (DPO approval signature)

Submit to DPO at least **5 business days** before the processing activity goes to production.

---

## Data Subject Rights Implementation (Art. 18)

| Right                                  | Response deadline | Implementation                                       |
| -------------------------------------- | ----------------- | ---------------------------------------------------- |
| Access (Art. 18(I))                    | 15 days           | Export all data held for the subject                 |
| Correction (Art. 18(III))              | 15 days           | Update inaccurate fields                             |
| Anonymisation / Deletion (Art. 18(IV)) | 15 days           | Hard-delete L1/L2 fields; pseudonymise audit records |
| Portability (Art. 18(V))               | 15 days           | Export in structured, machine-readable format        |
| Revocation of consent (Art. 18(IX))    | Immediate         | Disable processing; trigger deletion workflow        |

All rights requests are handled by the DPO. Engineering implements the technical capability; DPO manages the data subject interaction.

---

## Breach Notification (Art. 48)

When a breach affecting personal data is detected:

1. Contain the breach immediately (see `docs/runbooks/disaster-recovery.md` Scenario 5)
2. Notify DPO within **2 hours** of detection
3. DPO assesses severity and notifies ANPD within the required timeframe
4. If data subjects are at risk: DPO notifies affected subjects
5. Document: what happened, data affected, measures taken, timeline

The GDPR 72-hour clock and LGPD notification requirements run concurrently if EU data subjects are also affected.
