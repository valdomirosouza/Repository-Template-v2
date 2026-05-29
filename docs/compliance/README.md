# Compliance & Control Mapping

> **Purpose.** This directory is the **evidence package** an enterprise customer's security
> or procurement team needs when running a vendor risk assessment against a system built on
> this template. It maps the repository's controls to recognised frameworks, states what is
> **implemented vs. partial vs. planned**, and tracks the gaps to closure.
>
> **Status:** Living self-assessment · **Last updated:** 2026-05-29

---

## Audience

- **External** — enterprise prospects/clients completing a security questionnaire (SIG / CAIQ),
  requesting a SOC 2 report, an ISO 27001 statement, or a DPA. Start with
  [`trust-summary.md`](trust-summary.md) and [`security-questionnaire-quickref.md`](security-questionnaire-quickref.md).
- **Internal** — engineering, security, and SRE leads driving the controls to an auditable
  state. Start with the [control matrix](iso27001-annex-a-control-matrix.md) and the
  [remediation register](remediation-register.md).

## Documents

| Document                                                                   | Purpose                                                       | Status       |
| -------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------ |
| [`iso27001-annex-a-control-matrix.md`](iso27001-annex-a-control-matrix.md) | All 93 ISO/IEC 27001:2022 Annex A controls, status + evidence | ✅ This wave |
| [`soc2-tsc-mapping.md`](soc2-tsc-mapping.md)                               | SOC 2 Trust Services Criteria → repo evidence                 | ⏳ Wave 2    |
| [`slsa-supply-chain-assessment.md`](slsa-supply-chain-assessment.md)       | SLSA v1.0 build/release maturity assessment                   | ⏳ Wave 2    |
| [`remediation-register.md`](remediation-register.md)                       | Prioritised gap closure with owners + targets                 | ⏳ Wave 3    |
| [`trust-summary.md`](trust-summary.md)                                     | One-page security posture for prospects                       | ⏳ Wave 4    |
| [`security-questionnaire-quickref.md`](security-questionnaire-quickref.md) | Reusable answers to common questionnaire items                | ⏳ Wave 4    |

## Frameworks referenced

| Framework                     | Version                          | Used for                                          |
| ----------------------------- | -------------------------------- | ------------------------------------------------- |
| ISO/IEC 27001 Annex A         | **2022** (93 controls, 4 themes) | Primary control spine                             |
| SOC 2 Trust Services Criteria | 2017 (rev. 2022)                 | Cross-mapping for US enterprise buyers            |
| SLSA                          | **v1.0**                         | Build/release supply-chain integrity              |
| GDPR / LGPD                   | —                                | Privacy (DPIA / RIPD, RoPA — see `docs/privacy/`) |
| EU AI Act · NIST AI RMF       | —                                | AI governance (see `docs/ai-governance/`)         |

## Status legend

| Status             | Meaning                                                                                                                                            |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✅ **Implemented** | Control is in place and evidenced by an artifact or enforced gate in this repo.                                                                    |
| 🟡 **Partial**     | Control is designed/documented but not fully enforced, or depends on an unfilled org role.                                                         |
| ⏳ **Planned**     | Tracked in the [remediation register](remediation-register.md); not yet in place.                                                                  |
| ⬜ **N/A**         | Out of scope for a software template — satisfied by the **adopting organization** or the **cloud provider** under the shared-responsibility model. |

## Scope & boundaries — read this first

This is a **self-assessment of the controls that can be evidenced within the repository/template**.
It is **not a certification** and does not by itself constitute SOC 2 or ISO 27001 compliance.

The template is the _technical and procedural substrate_. To reach a certifiable posture, the
**adopting organization** must additionally provide the controls that require an operating
business — HR/personnel security, physical security, legal/supplier agreements, management
review, and a defined risk-treatment process — and must **fill the placeholder roles** referenced
in `.github/CODEOWNERS` (`@org/security-lead`, `@org/dpo`, `@org/sre-lead`, etc.) with real
owners. Controls of this kind are marked **⬜ N/A** with a note identifying who owns them.

Physical controls (ISO Annex A §7) are **inherited** from the cloud provider (AWS) under the
shared-responsibility model and covered by the provider's own SOC 2 / ISO 27001 attestations.

## Keeping this current

Update this package whenever a control's status changes — in the **same PR** that changes the
control. The [remediation register](remediation-register.md) is the backlog; when an item lands,
flip its matrix row from 🟡/⏳ to ✅ and cite the new evidence path. Review the whole package at
each release and at minimum quarterly.
