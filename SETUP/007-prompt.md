# Prompt 007 — CI/CD Pipelines + Harness

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section 2 — CI/CD Pipeline).
> Skip any file that already exists with real content.

---

## Task

Create all CI/CD workflow files, GitHub configuration files, and harness files
with **real, substantive content**.

---

## Part A — GitHub Workflows (`.github/workflows/`)

### `.github/workflows/ci.yml`

Full CI pipeline — 5 stages. Trigger: `push` to any branch and `pull_request`.

**Stage 1 — VALIDATE:**

- `lint`: ruff check + mypy
- `type-check`: mypy strict mode
- `secret-detection`: detect-secrets scan; zero findings = blocker
- `dependency-audit`: pip-audit; zero critical CVEs = blocker
- `spec-compliance-check`: verify PR body references a spec path (`specs/*`)
- `iac-scan`: checkov on `infrastructure/terraform/`
- `license-check`: license-checker; fail on GPL in production deps

**Stage 2 — TEST:**

- `unit-tests`: pytest `tests/unit/` with coverage report; fail if coverage < 80%
- `integration-tests`: docker-compose -f docker-compose.test.yml up + pytest `tests/integration/`
- `contract-tests`: pytest `tests/contract/`
- `observability-validation`: verify OTel propagation and metric label correctness

**Stage 3 — SECURITY:**

- `sast`: semgrep with `p/python` and `p/secrets` rulesets; zero HIGH/CRITICAL = blocker
- `sca`: pip-audit + safety; zero critical vulnerabilities
- `container-scan`: trivy image scan; zero CRITICAL CVEs = blocker
- `pii-scan`: grep test fixtures for real PII patterns (emails, CPF format,
  real IP ranges); fail on match

**Stage 4 — BUILD:**

- `build-artifact`: docker build multi-stage
- `sign-artifact`: cosign sign with keyless signing (OIDC)
- `generate-sbom`: syft + cyclonedx output; upload as artifact
- `push-to-registry`: push to container registry (conditional on main branch)

**Stage 5 — STAGING DEPLOY** (only on `main` branch):

- `helm-deploy`: helm upgrade --install to staging namespace
- `smoke-tests`: run `infrastructure/scripts/deploy/smoke-test.sh`
- `dast`: OWASP ZAP baseline scan against staging; zero critical findings = blocker
- `performance-baseline`: k6 smoke test against staging

Use GitHub Actions syntax. Use `actions/checkout@v4`, `actions/setup-python@v5`.
Define jobs with `needs:` dependencies. Add `concurrency:` group to cancel stale runs.

---

### `.github/workflows/cd-staging.yml`

CD to staging. Trigger: workflow_call or manual dispatch.
Steps: build → tag image with `staging-<sha>` → push → helm upgrade staging →
smoke test → notify Slack (placeholder step).

---

### `.github/workflows/cd-production.yml`

CD to production with canary deploy and Golden Signals gate.
Trigger: manual dispatch with `environment: production` protection rule.

Required inputs: `version`, `strategy` (canary | blue-green | rolling).

Canary steps:

1. Deploy 5% canary (`helm upgrade --set canary.weight=5`)
2. Wait 15 minutes — monitor Golden Signals via Prometheus query step
3. Check: error rate < SLO threshold AND p99 latency < SLO target
4. If gate passes → promote to 25% → repeat gate check
5. If gate passes → promote to 100% → full deploy
6. If gate fails at any step → automatic rollback via `rollback.sh`

Include a `check-error-budget` job that queries Prometheus and fails if
remaining error budget < 10%.

---

### `.github/workflows/sbom.yml`

SBOM generation and signing. Trigger: push to `main` and weekly schedule.
Steps: checkout → syft generate `sbom.cyclonedx.json` → cosign attest SBOM
to container image → upload SBOM as release artifact.

---

### `.github/workflows/secret-scanning.yml`

Secret detection. Trigger: push and pull_request.
Steps: checkout → detect-secrets scan `--baseline .secrets.baseline` →
fail on any new detected secret → upload report as artifact.
Include a comment step that posts findings as a PR comment when secrets detected.

---

### `.github/workflows/release.yml`

Release Please automation. Trigger: push to `main`.
Steps: release-please-action → on release created: build final image →
tag with SemVer → push to registry → generate and attach SBOM → create
GitHub release with CHANGELOG section as body.

---

## Part B — GitHub Configuration

### `.github/pull_request_template.md`

PR template with all required fields:

```markdown
## Summary

<!-- One paragraph description of the change -->

## Linked Issue

Closes #<!-- issue number -->

## Referenced Spec

<!-- Path to the spec governing this change, e.g. specs/ai/guardrails.md -->

## Impacted ADRs

<!-- List any ADRs this change relates to or supersedes -->

## Change Type

- [ ] Standard (minor enhancement or bug fix)
- [ ] Normal (requires RFC and CAB review)
- [ ] Emergency (hotfix — RFC filed within 24h post-merge)

## Deploy Script

<!-- Command to deploy this change, e.g. make deploy-staging -->

## Rollback Plan

<!-- How to revert this change if it causes issues in production -->

## Privacy Impact

- [ ] This change introduces or modifies personal data processing
  - If yes, DPIA/RIPD reference: <!-- docs/privacy/dpia/dpia-vN.md -->

## Checklist

- [ ] Tests written and passing (coverage ≥ 80%)
- [ ] No secrets or real PII in any changed file
- [ ] CHANGELOG.md updated under [Unreleased]
- [ ] Spec updated if implementation diverged from it
- [ ] ADR filed if an architectural decision was made
- [ ] Guardrails unmodified or strengthened (never weakened)
```

---

### `.github/CODEOWNERS`

Code owners mapped to the directory structure:

```
# Global fallback
*                           @org/engineering-team

# Governance
CLAUDE.md                   @org/tech-lead
docs/adr/                   @org/tech-lead
specs/                      @org/tech-lead @org/product-owner

# Privacy — DPO required
docs/privacy/               @org/dpo @org/tech-lead
specs/privacy/              @org/dpo @org/tech-lead
PRIVACY.md                  @org/dpo

# AI Governance
docs/ai-governance/         @org/ai-governance-lead @org/tech-lead
specs/ai/                   @org/ai-governance-lead @org/tech-lead

# Security — Security Lead required for guardrails
src/guardrails/             @org/security-lead @org/tech-lead
docs/security/              @org/security-lead
.github/workflows/          @org/devops-lead @org/security-lead

# SRE
docs/sre/                   @org/sre-lead
infrastructure/             @org/devops-lead @org/sre-lead

# Source code
src/agents/hitl_gateway.py  @org/security-lead @org/ai-governance-lead
src/agents/                 @org/ai-governance-lead @org/tech-lead
src/observability/          @org/sre-lead
src/shared/                 @org/tech-lead

# Tests
tests/security/             @org/security-lead
tests/                      @org/engineering-team

# Change management
docs/change-management/     @org/tech-lead @org/sre-lead
harness/                    @org/devops-lead
```

---

### `.github/ISSUE_TEMPLATE/change_request.md`

Change request issue template. Include YAML front matter with name, description,
labels, and assignees. Body with required fields:

- Problem description / motivation
- Referenced spec (`specs/*`)
- Change type: Standard | Normal | Emergency
- Estimated impact (affected services / data flows)
- Acceptance criteria (Given / When / Then)
- Rollback plan
- Privacy impact (Y/N; if Y, DPIA/RIPD required)

---

### `.github/ISSUE_TEMPLATE/bug_report.md`

Bug report template. Include YAML front matter. Body with:

- Describe the bug (actual vs expected behaviour)
- Steps to reproduce
- Environment (service name, version, environment: staging/production)
- Logs / traces (trace_id if available — **do not include real PII**)
- Severity (P1 Critical / P2 High / P3 Medium / P4 Low)
- Affected SLO (if applicable)

---

## Part C — Harness Files (`harness/`)

### `harness/code-check.yml`

PR gate harness. Defines the checks that must pass before a PR can merge:

- lint (ruff + mypy)
- unit-tests (coverage ≥ 80%)
- sast (semgrep — zero HIGH/CRITICAL)
- secret-detection (zero findings)
- pii-scan (no real PII in test fixtures)
- spec-compliance (spec path referenced in PR)

Structure as a YAML document with `gates:` list, each gate having:
`name`, `command`, `blocking: true`, `failure_message`.

---

### `harness/staging-check.yml`

Staging gate harness. Checks that must pass before promoting from staging:

- integration-tests
- dast (OWASP ZAP — zero critical)
- performance-baseline (k6 p99 < 500ms at baseline load)
- golden-signals-check (error rate < 1%, p99 latency < 500ms for 5 min)
- pii-validation (no PII in staging logs — automated grep check)

---

### `harness/release-check.yml`

Release gate harness. Checks required before a production release:

- sbom-generated (sbom.cyclonedx.json present and signed)
- error-budget-check (remaining budget > 10%)
- prr-complete (PRR checklist YAML all items checked)
- dpia-ripd-current (DPIA and RIPD versions match current processing)
- manual-approval (RFC approved by CAB)

---

### `harness/doc-check.yml`

Documentation gate harness. Checks:

- changelog-updated (CHANGELOG.md modified in this PR or branch)
- spec-exists (referenced spec file exists in `specs/`)
- adr-current (if ADR referenced, file exists in `docs/adr/`)
- runbook-linked (if new service, runbook exists in `docs/runbooks/`)

---

### Validation

After creating all files, confirm:

- All 6 workflow files exist in `.github/workflows/`
- `.github/CODEOWNERS` maps entries for every top-level `src/` subdirectory
- `.github/pull_request_template.md` contains the Privacy Impact and Checklist sections
- All 4 harness files exist with `gates:` or equivalent structured content
- `cd-production.yml` contains the canary weight promotion logic (5% → 25% → 100%)
