# Skill: DevSecOps Pipeline Security

## Purpose

Enforce security gates at every stage of the CI/CD pipeline following the
"shift-left" principle: catch vulnerabilities before they reach production.

## When to Activate

- Any CI/CD pipeline modification (`.github/workflows/`)
- Any `Dockerfile` or base image change
- Any infrastructure code change (`infrastructure/terraform/`, `infrastructure/k8s/`, `infrastructure/helm/`)
- Any dependency or package version change
- SLSA provenance or SBOM work

## Pipeline Security Stage Map

```
Code Commit
  └── Pre-commit hooks (local — .pre-commit-config.yaml)
       ├── detect-secrets    — blocks secrets from entering repo
       ├── ruff + bandit     — Python SAST (immediate feedback)
       └── gitleaks          — git history secret scan

CI — validate stage (ci.yml)
  ├── SAST:    Semgrep (Python/Go), SpotBugs (Java), gosec (Go), Bandit (Python)
  ├── SCA:     OWASP dep-check (Java), pip-audit (Python), nancy (Go), npm audit (Node)
  ├── Secrets: detect-secrets baseline check + Gitleaks full history scan
  └── IaC:     Checkov on infrastructure/terraform/, infrastructure/k8s/, infrastructure/helm/

CI — build stage
  ├── Container scan: Trivy (zero CRITICAL CVEs — blocks build)
  ├── SBOM generation: Syft → CycloneDX JSON
  ├── Artifact signing: Cosign (SLSA Level 3 provenance)
  └── License check: license-checker (no GPL/AGPL in production images)

CD — staging stage (cd-staging.yml)
  ├── DAST: OWASP ZAP full scan (zero CRITICAL findings — blocks promotion)
  ├── Performance baseline: k6 (p95 latency ≤ SLO threshold)
  └── Smoke tests: functional + security headers check

CD — production stage (cd-production.yml, canary)
  ├── Error budget check: > 10% remaining
  ├── RFC approval validation: cab-check job
  ├── Cosign verify: signature present on image digest
  └── Golden Signal monitoring: 15min observation window per canary step
```

## GitHub Actions Security Hardening

Apply to ALL workflow files in `.github/workflows/`:

```yaml
permissions: # Principle of least privilege
  contents: read
  packages: write # Only on build jobs
  id-token: write # Only on signing jobs (Cosign OIDC)
  security-events: write # Only on SAST upload jobs

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30 # Prevent runaway jobs
    steps:
      - uses: actions/checkout@<SHA> # SHA-pinned, not @v4
        with:
          fetch-depth: 0 # For gitleaks history scan
          persist-credentials: false # Reduce token exposure
```

## IaC Security Scan (Checkov)

```yaml
- name: IaC Security Scan
  uses: bridgecrewio/checkov-action@<SHA>
  with:
    directory: infrastructure/
    framework: terraform,helm,kubernetes
    soft_fail: false # Blocking
    output_format: sarif
    output_file_path: checkov-results.sarif

- name: Upload Checkov SARIF
  uses: github/codeql-action/upload-sarif@<SHA>
  with:
    sarif_file: checkov-results.sarif
```

## Secret Scanning Enhancement

Gitleaks full history scan — add to `ci.yml` alongside detect-secrets:

```yaml
- name: Gitleaks full history scan
  uses: gitleaks/gitleaks-action@<SHA>
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}
```

## Container Hardening Standards

```dockerfile
# Pin base image to digest (not tag)
FROM python:3.13-slim@sha256:<pinned-digest>

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# Read-only filesystem enforced in Helm chart:
# securityContext.readOnlyRootFilesystem: true

# No privileged capabilities — Helm chart:
# securityContext.capabilities.drop: [ALL]
```

## SBOM + Provenance Workflow

```yaml
- name: Generate SBOM
  run: syft . -o cyclonedx-json > sbom.json

- name: Sign image and attach SBOM
  run: |
    cosign sign --yes $IMAGE_DIGEST
    cosign attest --yes --predicate sbom.json --type cyclonedx $IMAGE_DIGEST

- name: Verify on deploy
  run: |
    cosign verify $IMAGE_DIGEST \
      --certificate-identity-regexp ".*" \
      --certificate-oidc-issuer "https://token.actions.githubusercontent.com"
```

## Harness Checks (advisory → blocking progression)

| Check ID | Description                               | Current Severity |
| -------- | ----------------------------------------- | ---------------- |
| DSEC-01  | Dockerfile uses digest-pinned base image  | WARNING          |
| DSEC-02  | GitHub Actions use SHA-pinned versions    | WARNING          |
| DSEC-03  | Workflow `permissions:` explicitly scoped | WARNING          |

Promote DSEC-01 and DSEC-02 to BLOCKING after the SHA-pinning migration sprint is complete.

## Spec Reference

`docs/adr/ADR-0029-devsecops-pipeline-security.md` — decision rationale, IaC scan policy, DAST gate policy, SLSA Level 3 target.
