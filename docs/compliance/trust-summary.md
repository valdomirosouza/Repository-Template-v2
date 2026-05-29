# Security & Trust Summary

> **One-page security posture** for prospective customers and their security/procurement teams.
> Backed by the detailed control mapping in this directory. **Last updated:** 2026-05-29.

> **Honest framing:** this product is built on a security- and privacy-by-design platform with
> an extensive, evidenced control set. It is **not yet independently certified** (SOC 2 / ISO
> 27001 in progress). We share our control matrix, gap register, and remediation roadmap openly —
> see the linked artifacts. We do not claim controls we cannot evidence.

## At a glance

| Domain                   | Posture                                                                                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Secure SDLC**          | Spec-driven development; PRs gated on lint, type-checking, ≥80% test coverage, SAST, secret scanning, and PII checks before merge.                                    |
| **Application security** | SAST (Bandit/SpotBugs/gosec), DAST (OWASP ZAP at staging), dependency-vulnerability gating across Python/Java/Go/JS, and OWASP-LLM-Top-10 tests.                      |
| **Encryption**           | TLS 1.2+ in transit; AES-256-GCM for sensitive (L1/L2) data at rest; KMS-managed keys; `rediss://` enforced in production.                                            |
| **Access control**       | Least-privilege cloud identities (IRSA), code-ownership review rules, branch protection with required checks.                                                         |
| **Data privacy**         | PII classified L1–L4; masked before logs, LLM calls, and message bus; GDPR DPIA + LGPD RIPD + Records of Processing maintained; data-retention automation.            |
| **AI governance**        | Human-in-the-Loop approval for consequential agent actions; immutable audit trail; graduated autonomy behind governed feature flags; EU AI Act + NIST AI RMF mapping. |
| **Reliability**          | SLOs with error-budget policy; Golden-Signals monitoring; canary deploys with automated rollback; documented runbooks; chaos testing in staging.                      |
| **Supply chain**         | SBOM (CycloneDX + SPDX) on every release; keyless artifact signing (Cosign/Sigstore); targeting SLSA Level 2+.                                                        |

## Certifications & attestations

| Item                | Status                                                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| SOC 2 Type II       | **In progress** — design mapped (see [`soc2-tsc-mapping.md`](soc2-tsc-mapping.md)); audit period not yet commenced.                                    |
| ISO/IEC 27001:2022  | **Self-assessed** — full Annex A matrix available (see [`iso27001-annex-a-control-matrix.md`](iso27001-annex-a-control-matrix.md)); not yet certified. |
| SLSA (supply chain) | Build **L1, advancing to L2+** (see [`slsa-supply-chain-assessment.md`](slsa-supply-chain-assessment.md)).                                             |
| GDPR / LGPD         | DPIA / RIPD maintained (`docs/privacy/`); DPO approval being formalised.                                                                               |
| Penetration test    | Checklist + report location maintained (`specs/security/pentest-checklist.md`, `docs/security/pentest-reports/`).                                      |

## Known, tracked gaps (transparency)

We track every open item in the [remediation register](remediation-register.md). The two we
previously prioritised for enterprise engagement were **remediated on 2026-05-29**:

1. **Operator authentication on the human-approval endpoint** (REM-001 ✅) — the HITL decision
   endpoint now requires a JWT bearer token with an operator role; the approver identity is
   taken from the verified token, not the request body.
2. **Mandatory human review on changes** (REM-005 ✅) — auto-merge is now scoped to
   documentation-only and Dependabot PRs; all code, infrastructure, and workflow changes require
   human review.

Remaining open items (e.g. supplier-role sign-off, supply-chain hardening to SLSA L2+) are
prioritised in the register.

## Where to go deeper

- Control matrix → [`iso27001-annex-a-control-matrix.md`](iso27001-annex-a-control-matrix.md)
- SOC 2 mapping → [`soc2-tsc-mapping.md`](soc2-tsc-mapping.md)
- Questionnaire answers → [`security-questionnaire-quickref.md`](security-questionnaire-quickref.md)
- Vulnerability disclosure → `SECURITY.md` · Privacy → `PRIVACY.md` / `docs/privacy/`

_Contact: route security/compliance inquiries to the Security Lead (see `.github/CODEOWNERS`)._
