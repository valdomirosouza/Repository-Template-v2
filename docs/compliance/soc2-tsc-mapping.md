# SOC 2 — Trust Services Criteria Mapping

> Maps the AICPA **Trust Services Criteria** (2017, rev. 2022) to evidence in this repository,
> cross-referenced to the [ISO 27001 Annex A matrix](iso27001-annex-a-control-matrix.md). Most
> US enterprise buyers request **SOC 2** rather than ISO; this is the sheet to attach to those
> reviews. Status legend is in [`README.md`](README.md).
>
> **Categories assessed:** Security (Common Criteria — always required), **Availability**,
> **Confidentiality**, **Processing Integrity**, **Privacy**. **Last updated:** 2026-05-29.

> ⚠️ **A SOC 2 report is issued by an independent CPA firm after an audit period.** This sheet
> demonstrates _control design_ (Type I readiness); it is **not** a SOC 2 report and asserts no
> operating-effectiveness opinion (Type II).

---

## Common Criteria (Security)

| TSC           | Criterion (abbrev.)                                                          | Status         | Evidence                                                                                                 | ISO ref    |
| ------------- | ---------------------------------------------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------- | ---------- |
| **CC1.x**     | Control environment — integrity, governance, org structure                   | 🟡 Partial     | `CLAUDE.md` §1/§8, `.github/CODEOWNERS` (roles), `docs/adr/ADR-0001`                                     | 5.1, 5.2   |
| **CC2.x**     | Communication & information — policies communicated, internal/external comms | 🟡 Partial     | `SECURITY.md`, `docs/`, `CHANGELOG.md`, glossary                                                         | 5.1, 6.8   |
| **CC3.x**     | Risk assessment — objectives, risk ID, fraud, change risk                    | 🟡 Partial     | `specs/security/threat-model.md` (STRIDE), DPIA risk tables                                              | 5.7, 5.8   |
| **CC4.x**     | Monitoring activities — evaluations, deficiency comms                        | ✅ Implemented | Golden Signals, Prometheus alerts, `docs/audit/expert-audit-2026-05-26.md`                               | 8.16, 5.35 |
| **CC5.x**     | Control activities — selection/deployment of controls in tech & process      | ✅ Implemented | `harness/` gates, CI pipeline, pre-commit                                                                | 8.25, 5.36 |
| **CC6.1**     | Logical access — identification & authentication                             | 🟡 Partial     | JWT auth; HITL operator endpoint now authenticated (REM-001 ✅)                                          | 5.15, 8.5  |
| **CC6.2–6.3** | Access provisioning, modification, removal                                   | 🟡 Partial     | CODEOWNERS, branch protection, IRSA least-privilege                                                      | 5.18, 8.2  |
| **CC6.6**     | Boundary protection (external threats)                                       | 🟡 Partial     | Terraform layered SGs, TLS, rate limiting (slowapi)                                                      | 8.20, 8.22 |
| **CC6.7**     | Data in transit & removal                                                    | 🟡 Partial     | TLS 1.2+ (ADR-0019), masking before transfer; mTLS pending (REM-003)                                     | 5.14, 8.24 |
| **CC6.8**     | Malware / unauthorized software prevention                                   | 🟡 Partial     | Dep scanning + **Trivy image CVE scan in CI** (REM-006 ✅); admission-time verification = REM-011        | 8.7        |
| **CC7.1–7.2** | Detection & monitoring of anomalies                                          | ✅ Implemented | Burn-rate alerts, Golden Signals, OTel tracing                                                           | 8.15, 8.16 |
| **CC7.3–7.4** | Incident response & evaluation                                               | ✅ Implemented | `docs/runbooks/`, auto-rollback, escalation                                                              | 5.24, 5.26 |
| **CC7.5**     | Recovery from incidents                                                      | ✅ Implemented | `rollback-procedure.md` (RB-001), Helm rollback, feature-flag kill switch                                | 5.26, 8.14 |
| **CC8.1**     | **Change management**                                                        | 🟡 Partial     | RFC/CAB process, branch protection, required CI checks; auto-merge scoped to docs/deps only (REM-005 ✅) | 8.32, 5.3  |
| **CC9.1–9.2** | Risk mitigation & vendor/3rd-party risk                                      | 🟡 Partial     | SBOM + Cosign (supply chain); vendor agreements org-level                                                | 5.21, 5.19 |

## Availability (A1)

| TSC  | Criterion                                  | Status     | Evidence                                                  | ISO ref    |
| ---- | ------------------------------------------ | ---------- | --------------------------------------------------------- | ---------- |
| A1.1 | Capacity & performance monitoring          | 🟡 Partial | HPA, load-test gate (PRR), saturation metrics             | 8.6        |
| A1.2 | Backup, recovery, environmental protection | 🟡 Partial | RDS backups, multi-AZ prod, DR plan (PRR)                 | 8.13, 8.14 |
| A1.3 | Recovery testing                           | ⏳ Planned | Chaos experiments (staging) exist; full DR test org-level | 8.34       |

## Confidentiality (C1)

| TSC  | Criterion                                    | Status         | Evidence                                                          | ISO ref |
| ---- | -------------------------------------------- | -------------- | ----------------------------------------------------------------- | ------- |
| C1.1 | Identify & maintain confidential information | ✅ Implemented | `docs/privacy/pii-inventory.md` (L1–L4), data-processing-register | 5.12    |
| C1.2 | Disposal of confidential information         | 🟡 Partial     | `retention_job.py`, `data-retention-policy.md`                    | 8.10    |

## Processing Integrity (PI1)

| TSC       | Criterion                                           | Status     | Evidence                                                                                            | ISO ref |
| --------- | --------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------- | ------- |
| PI1.1–1.3 | Inputs/processing complete, valid, accurate, timely | 🟡 Partial | Input validation at boundaries, contract tests (Pact — provider verify roadmapped), idempotent HITL | 8.26    |
| PI1.4–1.5 | Output accuracy & storage                           | 🟡 Partial | Audit trail, immutable HITL decision records                                                        | 5.33    |

## Privacy (P1–P8) — summary

> Detailed evidence lives in `docs/privacy/` (DPIA, RIPD, RoPA, retention) and is also LGPD/GDPR
> mapped. SOC 2 Privacy maps closely to those.

| TSC | Criterion                                   | Status         | Evidence                                             |
| --- | ------------------------------------------- | -------------- | ---------------------------------------------------- |
| P1  | Notice & communication of privacy practices | 🟡 Partial     | `PRIVACY.md`, data-processing-register               |
| P2  | Choice & consent                            | ⏳ Planned     | Consent flows org/product-level                      |
| P3  | Collection (lawful, minimal)                | 🟡 Partial     | PII inventory + DPIA necessity assessment            |
| P4  | Use, retention & disposal                   | ✅ Implemented | `data-retention-policy.md`, `retention_job.py`       |
| P5  | Access (data-subject rights)                | 🟡 Partial     | DSAR process referenced in DPIA; endpoints org-level |
| P6  | Disclosure to third parties                 | ✅ Implemented | PII masking before LLM/broker (`pii_filter.py`)      |
| P7  | Quality                                     | 🟡 Partial     | Validation at boundaries                             |
| P8  | Monitoring & enforcement                    | 🟡 Partial     | PII-leakage CI gate, audit log                       |

---

## Readiness summary

**SOC 2 Type I (design) readiness: substantial.** Detection, monitoring, incident response, and
cryptography are well-evidenced. The two design deficiencies previously flagged — **CC6.1**
(HITL operator endpoint authentication) and **CC8.1** (change management vs. auto-merge) — were
**remediated on 2026-05-29** (REM-001, REM-005). Type II (operating effectiveness over a period)
additionally requires the placeholder roles to be filled and ~3–12 months of operating evidence
(tickets, CAB minutes, access reviews, alert/incident records).
