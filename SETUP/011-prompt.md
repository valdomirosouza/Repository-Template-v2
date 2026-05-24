# Prompt 011 — Validation & Summary

> **Requires:** All previous prompts (001–010) completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (full document).
>
> This prompt performs no file creation. It validates the scaffolded repository
> against all requirements and outputs a structured summary report.

---

## Task

Perform a full validation of the scaffolded monorepo and output the results
as a structured summary table. Do not create, edit, or delete any files.

---

## Validation Checks

Run each check below and record the result as **PASS**, **FAIL**, or **PARTIAL**
with a note on any gaps found.

---

### Check 1 — Directory Structure

Verify every directory listed in `MONOREPO-STRUCTURE-EN.md`
(Section "Repository Structure") exists.

Spot-check these critical paths:

- `src/agents/`, `src/guardrails/`, `src/observability/`, `src/shared/`
- `tests/unit/guardrails/`, `tests/security/`, `tests/chaos/runbooks/`
- `docs/adr/`, `docs/privacy/dpia/`, `docs/privacy/ripd/`, `docs/ai-governance/`
- `docs/sre/slo/`, `docs/sre/prr/`, `docs/sre/cuj/`
- `docs/change-management/rfc/`
- `infrastructure/monitoring/prometheus/rules/`
- `infrastructure/monitoring/grafana/dashboards/`
- `infrastructure/monitoring/opentelemetry/`
- `infrastructure/scripts/deploy/`
- `.github/workflows/`, `.github/ISSUE_TEMPLATE/`
- `harness/`, `skills/sre/`, `skills/ai/`, `skills/privacy/`, `skills/change-management/`
- `specs/system/`, `specs/ai/`, `specs/privacy/`

Report: count of directories found vs expected.

---

### Check 2 — All Required Files Present

Verify every file listed in the original task exists. Group by category:

**Root governance (10 files):**
`CLAUDE.md`, `README.md`, `CHANGELOG.md`, `SECURITY.md`, `PRIVACY.md`,
`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.env.example`, `Makefile`, `.gitignore`

**ADR files (5 files):**
`docs/adr/README.md`,
`docs/adr/ADR-0001-monorepo-structure-and-governance.md`,
`docs/adr/ADR-0010-agent-framework-selection.md`,
`docs/adr/ADR-0011-hitl-hotl-model.md`,
`docs/adr/ADR-0012-pii-masking-strategy.md`,
`docs/adr/ADR-0013-data-retention-policy.md`

**Core docs (2 files):**
`docs/glossary.md`, `docs/repo-structure.md`

**Privacy docs (5 files):**
`docs/privacy/pii-inventory.md`, `docs/privacy/data-retention-policy.md`,
`docs/privacy/data-processing-register.md`,
`docs/privacy/dpia/dpia-v1.md`, `docs/privacy/ripd/ripd-v1.md`

**AI Governance docs (4 files):**
`docs/ai-governance/model-card.md`, `docs/ai-governance/eu-ai-act-compliance.md`,
`docs/ai-governance/nist-ai-rmf.md`, `docs/ai-governance/autonomy-boundaries.md`

**SRE docs (5 files):**
`docs/sre/slo/slo.yaml`, `docs/sre/slo/error-budget-policy.md`,
`docs/sre/prr/PRR-TEMPLATE.md`, `docs/sre/prr/prr-checklist.yaml`,
`docs/sre/cuj/CUJ-001-user-request-processing.md`

**Change management + Runbooks (6 files):**
`docs/change-management/README.md`, `docs/change-management/RFC-TEMPLATE.md`,
`docs/change-management/CAB-PROCESS.md`,
`docs/runbooks/README.md`, `docs/runbooks/rollback-procedure.md`,
`docs/runbooks/disaster-recovery.md`

**Specs (10 files):**
`specs/README.md`, `specs/system/vision.md`, `specs/system/architecture.md`,
`specs/system/async-event-flow.md`, `specs/ai/agent-design.md`,
`specs/ai/hitl-hotl.md`, `specs/ai/guardrails.md`,
`specs/privacy/pii-inventory.md`, `specs/privacy/data-retention.md`,
`specs/privacy/dpia-ripd.md`

**CI/CD + Harness (14 files):**
`.github/workflows/ci.yml`, `.github/workflows/cd-staging.yml`,
`.github/workflows/cd-production.yml`, `.github/workflows/sbom.yml`,
`.github/workflows/secret-scanning.yml`, `.github/workflows/release.yml`,
`.github/pull_request_template.md`, `.github/CODEOWNERS`,
`.github/ISSUE_TEMPLATE/change_request.md`, `.github/ISSUE_TEMPLATE/bug_report.md`,
`harness/code-check.yml`, `harness/staging-check.yml`,
`harness/release-check.yml`, `harness/doc-check.yml`

**Infrastructure (6 files):**
`infrastructure/monitoring/prometheus/rules/golden-signals.yaml`,
`infrastructure/monitoring/grafana/dashboards/golden-signals.json`,
`infrastructure/monitoring/grafana/dashboards/sre-overview.json`,
`infrastructure/monitoring/opentelemetry/otel-collector.yaml`,
`infrastructure/scripts/deploy/deploy.sh`,
`infrastructure/scripts/deploy/rollback.sh`,
`infrastructure/scripts/deploy/smoke-test.sh`

**Skills (10 files):**
`skills/README.md`,
`skills/sre/golden-signals.md`, `skills/sre/prr.md`, `skills/sre/cuj.md`,
`skills/ai/guardrails.md`,
`skills/privacy/pii.md`, `skills/privacy/lgpd.md`, `skills/privacy/gdpr.md`,
`skills/change-management/rfc-process.md`,
`skills/change-management/deploy-rollback.md`

**Source code (9 files):**
`src/agents/hitl_gateway.py`,
`src/guardrails/pii_filter.py`, `src/guardrails/prompt_injection_guard.py`,
`src/guardrails/action_limits.py`, `src/guardrails/audit_logger.py`,
`src/observability/otel_setup.py`, `src/observability/metrics.py`,
`src/observability/logger.py`,
`src/shared/config.py`, `src/shared/models.py`

**Tests (6 files):**
`tests/README.md`,
`tests/unit/guardrails/test_pii_filter.py`,
`tests/unit/guardrails/test_prompt_injection_guard.py`,
`tests/security/test_owasp_llm_top10.py`,
`tests/security/test_pii_leakage.py`,
`tests/chaos/runbooks/game-day-playbook.md`

Report: count of files found vs expected per category, and list any missing files.

---

### Check 3 — ADR Index Consistency

Open `docs/adr/README.md` and read the master index table.
Verify that every ADR listed in the index table has a corresponding `.md` file
in `docs/adr/`. List any ADRs in the index that are missing their file.

---

### Check 4 — Specs Index Consistency

Open `specs/README.md` and read the ownership table.
Verify that every spec listed in the table has a corresponding file under `specs/`.
List any specs in the table that are missing their file.

---

### Check 5 — CLAUDE.md Skills Coverage

Open `CLAUDE.md` and read the Skill Activation Table.
Verify that every skill path referenced in that table exists as a file under `skills/`.
List any referenced skill paths that are missing.

---

### Check 6 — CODEOWNERS Directory Coverage

Open `.github/CODEOWNERS`.
Verify that it contains entries for the following critical paths:
`src/guardrails/`, `src/agents/hitl_gateway.py`, `docs/privacy/`,
`docs/ai-governance/`, `docs/adr/`, `.github/workflows/`,
`infrastructure/`, `tests/security/`.
List any critical paths that are absent from CODEOWNERS.

---

### Check 7 — No Real PII or Secrets

Scan all files for:

- Common secret patterns (the word `password`, `api_key`, `secret` assigned to
  a non-placeholder value — i.e., not `your-secret-here` or an env var reference)
- Real email addresses that are not clearly synthetic (not `@example.com`,
  not `@test.org`, not `@<placeholder>`)
- Real CPF/SSN patterns that are not all-zero synthetic values

Report any findings. Note: placeholder values like `your-secret-key-here`,
`fake@example.com`, and `000.000.000-00` are expected and should not be flagged.

---

### Check 8 — Empty Leaf Directories Have .gitkeep

Verify that every directory that contains no content files has a `.gitkeep` file.
Report any empty directories missing `.gitkeep`.

---

## Output Format

Output the validation results as a structured summary with three sections:

### Section A — File and Directory Count

```
Total directories created:     ___
Total files created:           ___
.gitkeep files placed:         ___
```

### Section B — Validation Results Table

| Check                        | Result                | Notes |
| ---------------------------- | --------------------- | ----- |
| 1. Directory structure       | PASS / FAIL / PARTIAL |       |
| 2. Required files present    | PASS / FAIL / PARTIAL |       |
| 3. ADR index consistency     | PASS / FAIL / PARTIAL |       |
| 4. Specs index consistency   | PASS / FAIL / PARTIAL |       |
| 5. CLAUDE.md skills coverage | PASS / FAIL / PARTIAL |       |
| 6. CODEOWNERS coverage       | PASS / FAIL / PARTIAL |       |
| 7. No real PII or secrets    | PASS / FAIL / PARTIAL |       |
| 8. .gitkeep completeness     | PASS / FAIL / PARTIAL |       |

### Section C — Gaps Found

List every gap discovered across all checks. For each gap:

- File or directory path
- Which check flagged it
- Recommended remediation (create file / add entry / add .gitkeep)

If no gaps are found, write: **"No gaps found — scaffold is complete."**

---

### Final Status

State one of:

- **SCAFFOLD COMPLETE** — all checks passed, no gaps found
- **SCAFFOLD COMPLETE WITH MINOR GAPS** — all critical files present; minor gaps noted
- **SCAFFOLD INCOMPLETE** — one or more critical files missing; list them
