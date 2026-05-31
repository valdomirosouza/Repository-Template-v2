# ADR-0029 — DevSecOps Pipeline Security Hardening

**Status:** Accepted
**Date:** 2026-05-31
**Authors:** Security Lead, DevOps Lead
**Reviewers:** Tech Lead, SRE Lead

---

## Context

The repository already has SAST (Bandit, SpotBugs, gosec), secret scanning (detect-secrets), and SBOM generation (Syft + Cosign). However, several shift-left security controls are missing or inconsistently applied:

- No IaC security scan (Checkov) on Terraform, Helm, and Kubernetes manifests
- No DAST gate in staging pipeline (OWASP ZAP baseline scan exists in harness but not in `cd-staging.yml` as a blocking job)
- GitHub Actions use tag-pinned actions (`@v4`) in some workflows rather than SHA-pinned
- No Gitleaks git history scan in CI (only pre-commit hook locally)
- Container base images pinned by tag, not digest, in some Dockerfiles
- Workflow `permissions:` blocks not consistently set to least-privilege across all workflows

The OWASP Top 10 requires continuous DAST verification at the API layer; SLSA Level 3 provenance requires SHA-pinned actions and digest-pinned base images.

---

## Decision

Enforce the following security hardening across the pipeline:

**1. IaC Security Scan (Checkov)** — added to `ci.yml` as a blocking gate on `infrastructure/` changes. SARIF output uploaded to GitHub Security tab.

**2. DAST (OWASP ZAP Full Scan)** — added to `cd-staging.yml` as a blocking job after smoke tests. Zero CRITICAL findings required for production promotion. Reports archived in `docs/security/zap-reports/`.

**3. SHA-pinned GitHub Actions** — all `uses:` references in `.github/workflows/` must use commit SHA, not version tag. Enforced by `harness/code-check.yml` DSEC-02 check (advisory initially, promoted to blocking after migration sprint).

**4. Gitleaks CI scan** — added to `ci.yml` alongside existing detect-secrets. Covers git history, not just staged changes.

**5. Container digest pinning** — Dockerfiles must use `FROM image@sha256:<digest>` for base images. Enforced by DSEC-01 harness check (advisory).

**6. Least-privilege workflow permissions** — all workflows must declare explicit `permissions:` blocks. `GITHUB_TOKEN` default write access disabled at org level. Enforced by DSEC-03 harness check.

**7. Non-root container user** — all service Dockerfiles must create and switch to a non-root `appuser`. Verified by Trivy misconfiguration scan.

These controls collectively target SLSA Level 3 provenance and address OWASP Top 10 A05 (Security Misconfiguration) and A08 (Software and Data Integrity Failures).

---

## Consequences

- Pipeline duration increases ~10–15 minutes for DAST (ZAP full scan on staging)
- Checkov blocking requires IaC remediation discipline — teams must fix infrastructure findings before merge
- SHA-pinning of GitHub Actions requires a migration sprint; Dependabot configured to keep SHA pins current
- Gitleaks may surface historical secrets in git history requiring key rotation
- `docs/security/zap-reports/` directory created; reports retained for 90 days in CI artifacts

---

## Alternatives Considered

**ZAP baseline scan only** — rejected as insufficient; baseline scan skips authenticated endpoints. Full scan with auth header required for comprehensive OWASP coverage.

**Semgrep Cloud (managed)** — valid complement to Bandit/gosec; deferred. Current SAST toolchain is sufficient for the current language mix.

**Renovate instead of Dependabot for SHA pinning** — valid; Dependabot chosen as it is already configured for dependency updates.
