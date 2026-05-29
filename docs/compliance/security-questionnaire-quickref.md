# Security Questionnaire Quick-Reference

> Reusable, honest answers to the items that recur in enterprise security questionnaires
> (SIG, CAIQ, bespoke). Answer key: **Yes** (evidenced) · **Partial** (in place but with a
> tracked gap) · **Roadmap** (planned, see register) · **Org** (the deploying organization owns).
> Cross-references point to evidence in this repo. **Last updated:** 2026-05-29.

> Keep answers truthful — every **Partial/Roadmap** links to a [remediation](remediation-register.md)
> item. Misrepresenting posture is itself a failed control.

## Governance & policy

| Question                                              | Answer            | Evidence                                                                          |
| ----------------------------------------------------- | ----------------- | --------------------------------------------------------------------------------- |
| Do you have a documented information security policy? | Partial           | `SECURITY.md`, `CLAUDE.md` (governance contract), `docs/adr/`                     |
| Are security roles and responsibilities defined?      | Partial (REM-009) | `.github/CODEOWNERS`, `CLAUDE.md` §8 — roles are placeholders pending real owners |
| Do you perform risk assessments / threat modeling?    | Yes               | `specs/security/threat-model.md` (STRIDE), DPIA risk tables                       |
| Independent security review performed?                | Partial           | `docs/audit/expert-audit-2026-05-26.md`; recurring cadence Roadmap                |

## Secure SDLC & change management

| Question                                              | Answer       | Evidence                                                                                                                                                                                   |
| ----------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Is security integrated into your SDLC?                | Yes          | `CLAUDE.md` SDD cycle, `harness/` gates, pre-commit                                                                                                                                        |
| Do all code changes require peer review before merge? | Yes          | CODEOWNERS + branch protection + required checks; `auto-merge.yml` is scoped to docs-only / Dependabot PRs, so all code/infra changes require human review (REM-005 ✅)                    |
| Are there automated quality/security gates in CI?     | Yes          | `harness/code-check.yml` (lint, ≥80% coverage, SAST, secret scan, PII scan) + `pr-governance.yml` (Conventional-Commit title, CHANGELOG, spec reference, version consistency — REM-008 ✅) |
| Is there a formal change-management / CAB process?    | Yes (design) | `skills/change-management/`, `docs/change-management/` (RFC + CAB)                                                                                                                         |
| Separate dev/test/prod environments?                  | Yes          | `infrastructure/terraform/environments/{dev,staging,production}`                                                                                                                           |

## Access control & authentication

| Question                         | Answer  | Evidence                                                                                                                                                                 |
| -------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Is access least-privilege?       | Partial | IRSA per-service (Terraform), CODEOWNERS, branch protection                                                                                                              |
| Are all endpoints authenticated? | Partial | The HITL operator decision endpoint now requires a JWT bearer token + operator role (REM-001 ✅); remaining public API endpoints are being brought under the same scheme |
| MFA for privileged access?       | Org     | Identity-provider / org responsibility                                                                                                                                   |
| Periodic access reviews?         | Org     | Process org-level                                                                                                                                                        |

## Data protection & privacy

| Question                                      | Answer  | Evidence                                                                  |
| --------------------------------------------- | ------- | ------------------------------------------------------------------------- |
| Is data encrypted in transit?                 | Yes     | TLS 1.2+ (ADR-0019), `rediss://` in prod                                  |
| Is sensitive data encrypted at rest?          | Yes     | AES-256-GCM `EncryptedField` for L1/L2, KMS-managed keys                  |
| Do you classify data?                         | Yes     | `docs/privacy/pii-inventory.md` (L1–L4)                                   |
| GDPR / LGPD compliant?                        | Partial | DPIA + RIPD + RoPA maintained; DPO sign-off being formalised (REM-009)    |
| Is PII shared with subprocessors/LLMs masked? | Yes     | `src/guardrails/pii_filter.py` masks before LLM/logs/broker               |
| Data retention & deletion enforced?           | Yes     | `data-retention-policy.md`, `src/jobs/retention_job.py`                   |
| Is real PII used in test data?                | No      | CI gate blocks real PII in fixtures (`pii-scan`); synthetic-only standard |

## Vulnerability & supply-chain management

| Question                           | Answer               | Evidence                                                                      |
| ---------------------------------- | -------------------- | ----------------------------------------------------------------------------- |
| Do you run SAST?                   | Yes                  | Bandit, SpotBugs, gosec, ruff `S` rules — CI-gated                            |
| Do you run DAST?                   | Partial (REM-004)    | OWASP ZAP at staging; not yet in CI                                           |
| Dependency vulnerability scanning? | Yes                  | pip-audit, govulncheck, OWASP Dependency-Check, pnpm audit (severity-gated)   |
| Container image scanning?          | Yes                  | Trivy scan in `ci.yml` build job; fails on fixable CRITICAL/HIGH (REM-006 ✅) |
| Do you produce an SBOM?            | Yes                  | Syft (CycloneDX + SPDX) on every release + weekly                             |
| Are build artifacts signed?        | Yes                  | Cosign keyless (Sigstore/OIDC) image + SBOM attestation                       |
| SLSA level?                        | L2 → L3 (REM-007 ✅) | See `slsa-supply-chain-assessment.md`                                         |
| Secret scanning in place?          | Yes                  | `detect-secrets` (pre-commit + CI)                                            |

## Logging, monitoring & incident response

| Question                            | Answer | Evidence                                                |
| ----------------------------------- | ------ | ------------------------------------------------------- |
| Centralised, structured logging?    | Yes    | `src/observability/logger.py` (JSON), OTel tracing      |
| Immutable audit trail?              | Yes    | `src/guardrails/audit_logger.py` (append-only)          |
| Security monitoring & alerting?     | Yes    | Golden Signals, Prometheus burn-rate alerts, Grafana    |
| Documented incident response?       | Yes    | `docs/runbooks/`, escalation paths, post-mortem cadence |
| Defined SLAs for incident response? | Yes    | `SECURITY.md` (disclosure SLAs), error-budget policy    |

## Resilience & business continuity

| Question             | Answer  | Evidence                                                                              |
| -------------------- | ------- | ------------------------------------------------------------------------------------- |
| Automated backups?   | Partial | RDS automated backups (Terraform)                                                     |
| High availability?   | Partial | Multi-AZ production, replicas, PodDisruptionBudget                                    |
| Rollback capability? | Yes     | Canary + auto-rollback (`cd-production.yml`), Helm rollback, feature-flag kill switch |
| DR plan and testing? | Partial | DR in PRR; chaos testing in staging; full DR test Org                                 |

## AI governance (if applicable to the engagement)

| Question                         | Answer  | Evidence                                                                       |
| -------------------------------- | ------- | ------------------------------------------------------------------------------ |
| Human oversight of AI actions?   | Yes     | HITL gateway — consequential actions require human approval                    |
| Is autonomous mode controllable? | Yes     | Graduated autonomy via governed feature flags; FULL requires ADR-0015 sign-off |
| Audit trail of AI decisions?     | Yes     | Immutable audit log with `agent_id`, `trace_id`, approver identity             |
| Alignment to AI regulation?      | Partial | EU AI Act (Arts. 9/12–14) + NIST AI RMF mapping in `docs/ai-governance/`       |

---

_For any **Partial/Roadmap** answer, the linked `REM-` item in the
[remediation register](remediation-register.md) gives owner, severity, and target._
