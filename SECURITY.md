# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✓ Active  |

---

## Compliance & Control Mapping

Our security control posture — mapped to **ISO/IEC 27001:2022**, **SOC 2** Trust Services
Criteria, and **SLSA** — along with a prospect-facing trust summary and reusable
security-questionnaire answers, is maintained in
[`docs/compliance/`](docs/compliance/README.md). Known gaps are tracked openly in the
[remediation register](docs/compliance/remediation-register.md).

---

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

### Preferred method: GitHub Security Advisories

Use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) for this repository.

### Alternative: Email

Send a detailed report to: **security@<org-domain>**

Encrypt sensitive reports with the team PGP key (key ID: `<KEY-ID>`, published on `keys.openpgp.org`).

---

## What to Include in Your Report

- **Description:** Clear description of the vulnerability and its potential impact
- **Type:** e.g., SQL injection, prompt injection, PII leakage, authentication bypass
- **Affected component:** File paths, API endpoints, or agent actions involved
- **Steps to reproduce:** Minimal reproduction steps or proof-of-concept
- **CVSS score** (if you have assessed it)
- **Suggested fix** (optional but appreciated)

---

## Response Timeline

| Stage                              | SLA              |
| ---------------------------------- | ---------------- |
| Initial acknowledgement            | 48 hours         |
| Triage and severity classification | 5 business days  |
| Fix timeline communicated          | 10 business days |
| Critical / High CVE fix deployed   | 14 days          |
| Medium CVE fix deployed            | 30 days          |
| Low CVE fix deployed               | 90 days          |

---

## Scope

### In scope

- All services and APIs in this repository
- Authentication and authorization controls
- AI agent guardrails and HITL/HOTL controls
- PII handling and privacy controls
- Infrastructure configuration (Helm, Terraform)
- CI/CD pipeline security
- Dependency vulnerabilities

### Out of scope

- Third-party services and LLM providers (report directly to the provider)
- Issues already known and tracked in our public issue tracker
- Denial-of-service attacks
- Social engineering

---

## AI-Specific Security

This system incorporates AI agents. We are particularly interested in reports of:

- **Prompt injection** (OWASP LLM01): inputs that manipulate agent behavior
- **Sensitive information disclosure** (OWASP LLM06): PII leaking through LLM outputs
- **Excessive agency** (OWASP LLM08): agents performing actions beyond their defined scope
- **HITL bypass**: any mechanism that allows agent actions to skip human approval
- **Audit log tampering**: any mechanism to alter or delete immutable audit records

---

## Disclosure Policy

We follow **coordinated disclosure**:

1. Reporter notifies us privately.
2. We confirm the vulnerability and begin work on a fix.
3. We agree on a disclosure date (maximum 90 days from report).
4. We publish a security advisory and release a patched version.
5. Reporter may publish their findings after the patch is released.

We will credit reporters in our security advisories unless anonymity is requested.

---

## Bug Bounty

There is currently no bug bounty programme. We recognise responsible disclosure by crediting reporters in security advisories and release notes.

---

## Personal Data in Security Reports

Security reports may contain personal data (e.g., usernames, email addresses found through investigation). We handle this data under our Privacy Policy (`PRIVACY.md`) and will delete it once the issue is resolved.
