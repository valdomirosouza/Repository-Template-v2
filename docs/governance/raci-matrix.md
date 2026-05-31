# RACI Matrix

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** Tech Lead
> **Related:** `docs/governance/owner-onboarding.md` · `.github/CODEOWNERS` · `docs/compliance/iso27001-annex-a-control-matrix.md`

RACI defines accountability for every key process in this system.

| Symbol | Meaning                                                                   |
| ------ | ------------------------------------------------------------------------- |
| **R**  | **Responsible** — does the work                                           |
| **A**  | **Accountable** — owns the outcome; signs off; only one per row           |
| **C**  | **Consulted** — provides input before the decision; two-way communication |
| **I**  | **Informed** — notified of the outcome; one-way communication             |

**Role abbreviations:**

| Abbr  | Role                    | CODEOWNERS slug                |
| ----- | ----------------------- | ------------------------------ |
| TL    | Tech Lead               | `@your-org/tech-lead`          |
| PO    | Product Owner           | —                              |
| ENG   | Engineering Team        | `@your-org/engineering-team`   |
| SEC   | Security Lead           | `@your-org/security-lead`      |
| DPO   | Data Protection Officer | `@your-org/dpo`                |
| AIGOV | AI Governance Lead      | `@your-org/ai-governance-lead` |
| SRE   | SRE Lead                | `@your-org/sre-lead`           |
| DEV   | DevOps Lead             | `@your-org/devops-lead`        |

---

## 1. Software Development Lifecycle

| Process                                                           | TL    | PO  | ENG     | SEC   | DPO   | AIGOV | SRE | DEV |
| ----------------------------------------------------------------- | ----- | --- | ------- | ----- | ----- | ----- | --- | --- |
| Write or update a spec (`specs/`)                                 | C     | A   | R       | C     | C     | C     | —   | —   |
| Implement a feature (SDD Steps 6–7)                               | C     | I   | **R/A** | —     | —     | —     | —   | —   |
| Code review — general PR                                          | A     | —   | R       | —     | —     | —     | —   | —   |
| Code review — security-sensitive paths (`src/guardrails/`, auth)  | C     | —   | R       | **A** | —     | —     | —   | —   |
| Code review — AI agent paths (`src/agents/`, `hitl_gateway.py`)   | C     | —   | R       | C     | —     | **A** | —   | —   |
| Code review — privacy paths (PII, `src/guardrails/pii_filter.py`) | C     | —   | R       | C     | **A** | —     | —   | —   |
| Merge to `develop`                                                | **A** | —   | R       | —     | —     | —     | —   | —   |
| Merge `develop` → `main`                                          | **A** | —   | R       | —     | —     | —     | —   | —   |
| Author ADR                                                        | **A** | —   | R       | C     | C     | C     | C   | C   |
| Update `CHANGELOG.md`                                             | —     | —   | **R/A** | —     | —     | —     | —   | —   |

---

## 2. Security & Compliance

| Process                                                | TL  | PO  | ENG | SEC   | DPO | AIGOV | SRE | DEV     |
| ------------------------------------------------------ | --- | --- | --- | ----- | --- | ----- | --- | ------- |
| SAST / secret scanning gate (CI)                       | I   | —   | R   | **A** | —   | —     | —   | C       |
| SCA / dependency vulnerability triage                  | C   | —   | R   | **A** | —   | —     | —   | —       |
| Penetration test / DAST (OWASP ZAP)                    | C   | —   | —   | **A** | —   | —     | —   | R       |
| Threat model update (`specs/security/threat-model.md`) | C   | C   | R   | **A** | —   | —     | —   | —       |
| SOX audit evidence package _(if SOX applies)_          | C   | —   | —   | C     | —   | —     | —   | **A**   |
| SOX access review (quarterly) _(if SOX applies)_       | C   | —   | —   | **A** | —   | —     | —   | —       |
| SBOM generation and signing                            | I   | —   | —   | C     | —   | —     | —   | **R/A** |
| Container vulnerability remediation (Trivy)            | —   | —   | R   | C     | —   | —     | —   | **A**   |
| IaC security scan (Checkov)                            | —   | —   | R   | C     | —   | —     | —   | **A**   |
| Security incident response                             | C   | —   | C   | **A** | C   | —     | R   | R       |

---

## 3. Privacy & Data Protection

| Process                                                | TL  | PO  | ENG | SEC | DPO   | AIGOV | SRE | DEV |
| ------------------------------------------------------ | --- | --- | --- | --- | ----- | ----- | --- | --- |
| PII classification (new data fields)                   | C   | C   | R   | C   | **A** | —     | —   | —   |
| DPIA / RIPD review (new PII processing)                | C   | C   | R   | C   | **A** | —     | —   | —   |
| PII masking review (`pii_filter.py` changes)           | C   | —   | R   | C   | **A** | —     | —   | —   |
| LGPD / GDPR compliance sign-off                        | C   | C   | —   | C   | **A** | —     | —   | —   |
| Data subject access request (DSAR) response            | —   | —   | C   | —   | **A** | —     | —   | —   |
| Privacy policy update                                  | C   | C   | —   | —   | **A** | —     | —   | —   |
| PII inventory update (`docs/privacy/pii-inventory.md`) | C   | C   | R   | C   | **A** | —     | —   | —   |

---

## 4. AI Governance _(AI Agents Module — only when `src/agents/` is active)_

| Process                                                | TL    | PO  | ENG | SEC   | DPO | AIGOV | SRE | DEV |
| ------------------------------------------------------ | ----- | --- | --- | ----- | --- | ----- | --- | --- |
| New agent action type added                            | C     | C   | R   | C     | —   | **A** | —   | —   |
| HITL gateway change (`hitl_gateway.py`)                | C     | —   | R   | C     | —   | **A** | —   | —   |
| Autonomy level change (feature flag `autonomous-mode`) | C     | C   | —   | C     | —   | **A** | —   | —   |
| Guardrails change (`src/guardrails/`)                  | C     | —   | R   | **A** | —   | C     | —   | —   |
| Prompt injection guard modification                    | C     | —   | R   | **A** | —   | C     | —   | —   |
| HOTL (autonomous) mode activation                      | **A** | C   | —   | C     | —   | R     | C   | —   |
| AI bias / ethical review                               | C     | C   | R   | —     | —   | **A** | —   | —   |
| LLM model version change                               | C     | C   | R   | C     | —   | **A** | —   | —   |
| Agent audit log review                                 | —     | —   | —   | C     | C   | **A** | —   | —   |

---

## 5. Change Management & Release

| Process                                   | TL    | PO  | ENG   | SEC | DPO | AIGOV | SRE   | DEV   |
| ----------------------------------------- | ----- | --- | ----- | --- | --- | ----- | ----- | ----- |
| RFC authoring (Normal / Emergency change) | C     | C   | **R** | C   | —   | —     | —     | —     |
| CAB approval (Normal change)              | **A** | C   | —     | C   | —   | —     | C     | C     |
| CAB approval (Emergency change — async)   | **A** | —   | —     | C   | —   | —     | —     | —     |
| Standard change deploy                    | —     | —   | R     | —   | —   | —     | C     | **A** |
| Normal change deploy                      | C     | —   | R     | C   | —   | —     | C     | **A** |
| Emergency change deploy                   | **A** | —   | R     | C   | —   | —     | C     | R     |
| Rollback decision                         | C     | —   | —     | —   | —   | —     | **A** | R     |
| Post-mortem facilitation                  | C     | —   | C     | C   | —   | —     | **A** | C     |
| Release cut (`chore(release): x.y.z`)     | **A** | —   | R     | —   | —   | —     | —     | —     |
| Feature flag change                       | C     | C   | R     | —   | —   | **A** | —     | C     |

---

## 6. SRE & Observability

| Process                                    | TL    | PO  | ENG | SEC | DPO | AIGOV | SRE     | DEV |
| ------------------------------------------ | ----- | --- | --- | --- | --- | ----- | ------- | --- |
| SLO definition and target setting          | **A** | C   | C   | —   | —   | —     | R       | —   |
| SLO breach response (on-call)              | —     | —   | C   | —   | —   | —     | **R/A** | —   |
| Error budget policy enforcement            | C     | I   | —   | —   | —   | —     | **A**   | —   |
| Runbook authoring                          | C     | —   | C   | C   | —   | —     | **R/A** | —   |
| Runbook review (annual / post-incident)    | C     | —   | —   | C   | —   | —     | **A**   | —   |
| Grafana dashboard updates                  | —     | —   | R   | —   | —   | —     | **A**   | C   |
| Alert rule authoring                       | —     | —   | R   | C   | —   | —     | **A**   | C   |
| PRR (Production Readiness Review) sign-off | **A** | —   | R   | C   | —   | —     | C       | C   |
| DORA metrics retrospective (when < Elite)  | **A** | —   | C   | —   | —   | —     | R       | —   |
| Capacity planning                          | C     | C   | —   | —   | —   | —     | **A**   | C   |

---

## 7. Infrastructure & Pipeline

| Process                                        | TL    | PO  | ENG | SEC   | DPO | AIGOV | SRE | DEV     |
| ---------------------------------------------- | ----- | --- | --- | ----- | --- | ----- | --- | ------- |
| CI/CD pipeline change (`.github/workflows/`)   | C     | —   | C   | C     | —   | —     | C   | **R/A** |
| Infrastructure change (Terraform / Helm / K8s) | C     | —   | C   | C     | —   | —     | C   | **R/A** |
| Secret rotation                                | —     | —   | —   | **A** | —   | —     | —   | R       |
| CODEOWNERS update                              | **A** | —   | R   | C     | C   | C     | —   | —       |
| Dependabot / dependency update approval        | —     | —   | R   | C     | —   | —     | —   | **A**   |
| Container base image upgrade                   | —     | —   | R   | C     | —   | —     | —   | **A**   |
| Database migration (Alembic)                   | **A** | —   | R   | —     | —   | —     | C   | —       |
| Schema Registry (Avro) change                  | **A** | C   | R   | —     | —   | —     | C   | —       |

---

## RACI Validation Rules

When updating this matrix, verify:

1. Every row has **exactly one A** — if there is no accountable owner, assign one before merging.
2. The **A is never also R on the same row** for high-risk processes (security, AI governance, financial paths) — segregation of duties.
3. Any process touching `src/agents/hitl_gateway.py` has **both SEC and AIGOV** in the C or A column.
4. Any process touching PII fields has **DPO** in the A or C column.
5. Roles map to real individuals — verify against `docs/governance/owner-onboarding.md` quarterly.
