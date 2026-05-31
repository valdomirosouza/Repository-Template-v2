# Skill: ISO 27001 A.12.1 Change Management

## Purpose

Enforce ISO 27001 Annex A control A.12.1 (Operational Procedures and Responsibilities)
for all changes to production systems, with full deploy and rollback procedure documentation.

## When to Activate

- Any PR targeting production-impacting paths (`src/`, `services/`, `infrastructure/`, `.github/workflows/`)
- Any production deployment or rollback operation
- Any configuration change (secrets, feature flags, IaC)
- RFC drafting or CAB approval workflow

## Change Classification

### Standard Change

- Pre-approved, low-risk, repeatable.
- Label: `standard-change`
- Deploy window: Mon–Thu 10:00–17:00 local time.
- No CAB approval required.
- Automated pipeline approval if all gates pass.

### Normal Change

- Planned change requiring CAB review.
- Label: `normal-change`
- RFC required and approved **before** merge.
- RFC_ID must appear in merge commit message: `Refs: RFC-NNNN`.
- `cd-production.yml` runs `cab-check` job to verify RFC status = APPROVED.

### Emergency Change

- Critical fix for production incident.
- Label: `emergency-change`
- TL + SecOps async approval via `#cab-emergency` Slack channel.
- Retroactive RFC created within 24 hours.
- Post-mortem mandatory even if change was successful.

## Deploy Procedure (ISO 27001 Compliant)

```bash
# Step 1 — Pre-deploy checklist
make prr-check SERVICE=<name>          # Production Readiness Review
cat docs/sre/slo/slo.yaml              # Verify error budget > 10%
cat docs/change-log/latest.yaml        # Confirm RFC_ID recorded

# Step 2 — Build with integrity
make build SERVICE=<name> VERSION=x.y.z
make sbom                              # Generate CycloneDX SBOM
# cosign sign handled by cd-production.yml (SLSA provenance)

# Step 3 — Staging validation
make deploy-staging SERVICE=<name> VERSION=x.y.z
make smoke-test                        # Blocking — must pass
# OWASP ZAP DAST runs automatically in cd-staging.yml

# Step 4 — Canary production deploy
# cd-production.yml: 5% → (15min SLO observe) → 25% → (15min) → 100%
# Auto-rollback if error_rate > SLO threshold at any step

# Step 5 — Record change evidence
# Automatically appended by cd-production.yml record-change-evidence job
```

## Rollback Procedure (ISO 27001 Compliant)

```bash
# Automated rollback (triggered by SLO breach during canary)
# cd-production.yml rollback-on-failure job runs automatically

# Manual rollback
make rollback SERVICE=<name>
# Runs: helm rollback <release> --wait --timeout 5m

# Post-rollback validation
make smoke-test                        # Must pass on previous version
make golden-signals-check              # Confirm error rate below SLO threshold

# Post-rollback evidence recorded automatically by cd-production.yml
```

## Configuration Change Controls

- Feature flag changes in `infrastructure/feature-flags/` require ADR-0015 governance review.
- Secret rotation follows `docs/runbooks/secret-rotation.md`.
- Infrastructure changes (Terraform, Helm) require `checkov` IaC scan pass and TF plan review.
- Database migrations are Normal Changes by default (schema changes have high blast radius).

## Audit Evidence Matrix

| Control                         | Evidence                       | Location                     | Owner       |
| ------------------------------- | ------------------------------ | ---------------------------- | ----------- |
| A.12.1.1 Documented procedures  | This skill + CLAUDE.md §11     | `skills/`, `CLAUDE.md`       | Tech Lead   |
| A.12.1.2 Change management      | RFC + CAB approval record      | `docs/change-log/`           | DevOps Lead |
| A.12.1.3 Capacity management    | Grafana + Prometheus alerts    | `infrastructure/monitoring/` | SRE Lead    |
| A.12.1.4 Separation of dev/prod | Branch protection + CODEOWNERS | `.github/`                   | DevOps Lead |

## Spec Reference

`specs/compliance/iso27001-change-management.md` — classification matrix, deploy/rollback flowcharts, CAB integration, evidence retention requirements.
