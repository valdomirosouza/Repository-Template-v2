# SETUP — Scaffolding Execution Guide

> **Purpose:** Step-by-step prompts to scaffold the full monorepo from scratch using Claude Code.
> Each prompt is self-contained and must be executed in order, one session at a time.
> Reference document for all prompts: `MONOREPO-STRUCTURE-EN.md` (repo root).

---

## Why prompts are split

The original single-prompt scaffold was blocked by the API content filtering policy
because certain security and guardrail files (prompt injection guard, OWASP test harnesses)
triggered the filter when generated together with their surrounding context.

**Solution applied:**

1. Security-sensitive files were isolated into `010-prompt.md` with an explicit
   content policy header that frames all code as **defensive rejection logic**.
2. All test inputs use **synthetic placeholder tokens** — never real exploit strings.
3. All PII examples use **clearly fake data** (`fake@example.com`, `000.000.000-00`, RFC 5737 IPs).
4. Remaining prompts (001–009, 011) contain no filtering-risk content and can be
   run without special precautions.

---

## Execution Order

Run each prompt in a **separate Claude Code session**. Open the file, copy its
full contents into the prompt, and wait for completion before proceeding.

| #   | File            | Topic                                      | Est. files created  | Risk level   |
| --- | --------------- | ------------------------------------------ | ------------------- | ------------ |
| 1   | `001-prompt.md` | Directory scaffold + `.gitkeep` files      | ~55 dirs            | None         |
| 2   | `002-prompt.md` | Root governance files                      | 10 files            | None         |
| 3   | `003-prompt.md` | ADRs + Glossary + Repo structure           | 8 files             | None         |
| 4   | `004-prompt.md` | Privacy docs + AI Governance docs          | 9 files             | None         |
| 5   | `005-prompt.md` | SRE + Change Management + Runbooks         | 10 files            | None         |
| 6   | `006-prompt.md` | Specs (SDD)                                | 10 files            | None         |
| 7   | `007-prompt.md` | CI/CD workflows + Harness                  | 14 files            | None         |
| 8   | `008-prompt.md` | Infrastructure monitoring + Skills         | 13 files            | None         |
| 9   | `009-prompt.md` | Source code: agents, observability, shared | 7 files             | None         |
| 10  | `010-prompt.md` | Guardrails source + Security tests         | 8 files             | **Isolated** |
| 11  | `011-prompt.md` | Postmortem template                        | 1 file              | None         |
| 12  | `012-prompt.md` | Validation + Summary report                | 0 files (read-only) | None         |

**Total target:** ~152 files across ~80 directories.

---

## Prerequisites

Before running prompt 001, ensure:

- [ ] `MONOREPO-STRUCTURE-EN.md` is present at the repository root
- [ ] You are in the correct working directory (the monorepo root)
- [ ] Claude Code has write permissions to the working directory
- [ ] No prior partial scaffold exists that could conflict (or note which prompts to skip)

---

## How to run a prompt

```bash
# Option A — paste directly
# Open the .md file, copy all contents, paste into Claude Code prompt

# Option B — reference the file
# In Claude Code, type:
Read SETUP/001-prompt.md carefully and execute every instruction in it.
```

Both options work. Option B is preferred as Claude will read and execute without
manual copy-paste.

---

## Skipping already-completed prompts

Every prompt includes the instruction:

> _"Skip any file that already exists with real content."_

This means prompts are **idempotent** — safe to re-run. If a session was interrupted
mid-prompt, re-run the same prompt; existing files will be skipped and missing ones
will be created.

---

## Content Policy — What Changed in `010-prompt.md`

Prompt 010 handles the files most likely to trigger content filtering.
The following rules are embedded in that prompt's header and must be honoured:

| Rule                         | What it means                                                                           |
| ---------------------------- | --------------------------------------------------------------------------------------- |
| Structural patterns only     | Detection code uses format/shape matching, not stored exploit strings                   |
| Synthetic placeholder tokens | Test inputs use `SYNTHETIC_INJECT_ATTEMPT`, `SYNTHETIC_OVERRIDE_TOKEN`, etc.            |
| Clearly fake PII             | `fake@example.com`, `000.000.000-00`, `192.0.2.1` (RFC 5737 TEST-NET)                   |
| Reject, never reproduce      | Every guardrail returns a safe value or raises a rejection — never stores the bad input |
| Truncated logging            | Rejected inputs are logged as `sha256(input)[:16]` + reason only                        |

If prompt 010 is still blocked after applying these rules, split it further:
run `src/guardrails/pii_filter.py` alone first, then `prompt_injection_guard.py`,
then the test files.

---

## Validation

After completing all 12 prompts, run prompt 012 to get a full validation report.
The report checks:

| Check                     | What is verified                                |
| ------------------------- | ----------------------------------------------- |
| Directory structure       | All required directories exist                  |
| File presence             | All ~144 required files exist                   |
| ADR index consistency     | Every ADR in the index has a file               |
| Specs index consistency   | Every spec in the ownership table has a file    |
| CLAUDE.md skills coverage | Every skill path in the activation table exists |
| CODEOWNERS coverage       | All critical paths have an owner                |
| No real PII or secrets    | No unintended real data in any file             |
| `.gitkeep` completeness   | No empty directories without `.gitkeep`         |

Expected final status: **SCAFFOLD COMPLETE** or **SCAFFOLD COMPLETE WITH MINOR GAPS**.

---

## File Map — Prompt to Output

```
001  →  (directory tree only, no content files)

002  →  CLAUDE.md, README.md, CHANGELOG.md, SECURITY.md, PRIVACY.md,
        CONTRIBUTING.md, CODE_OF_CONDUCT.md, .env.example, Makefile, .gitignore

003  →  docs/adr/README.md
        docs/adr/ADR-0001-monorepo-structure-and-governance.md
        docs/adr/ADR-0010-agent-framework-selection.md
        docs/adr/ADR-0011-hitl-hotl-model.md
        docs/adr/ADR-0012-pii-masking-strategy.md
        docs/adr/ADR-0013-data-retention-policy.md
        docs/glossary.md
        docs/repo-structure.md

004  →  docs/privacy/pii-inventory.md
        docs/privacy/data-retention-policy.md
        docs/privacy/data-processing-register.md
        docs/privacy/dpia/dpia-v1.md
        docs/privacy/ripd/ripd-v1.md
        docs/ai-governance/model-card.md
        docs/ai-governance/eu-ai-act-compliance.md
        docs/ai-governance/nist-ai-rmf.md
        docs/ai-governance/autonomy-boundaries.md

005  →  docs/sre/slo/slo.yaml
        docs/sre/slo/error-budget-policy.md
        docs/sre/prr/PRR-TEMPLATE.md
        docs/sre/prr/prr-checklist.yaml
        docs/sre/cuj/CUJ-001-user-request-processing.md
        docs/change-management/README.md
        docs/change-management/RFC-TEMPLATE.md
        docs/change-management/CAB-PROCESS.md
        docs/runbooks/README.md
        docs/runbooks/rollback-procedure.md
        docs/runbooks/disaster-recovery.md

006  →  specs/README.md
        specs/system/vision.md
        specs/system/architecture.md
        specs/system/async-event-flow.md
        specs/ai/agent-design.md
        specs/ai/hitl-hotl.md
        specs/ai/guardrails.md
        specs/privacy/pii-inventory.md
        specs/privacy/data-retention.md
        specs/privacy/dpia-ripd.md

007  →  .github/workflows/ci.yml
        .github/workflows/cd-staging.yml
        .github/workflows/cd-production.yml
        .github/workflows/sbom.yml
        .github/workflows/secret-scanning.yml
        .github/workflows/release.yml
        .github/pull_request_template.md
        .github/CODEOWNERS
        .github/ISSUE_TEMPLATE/change_request.md
        .github/ISSUE_TEMPLATE/bug_report.md
        harness/code-check.yml
        harness/staging-check.yml
        harness/release-check.yml
        harness/doc-check.yml

008  →  infrastructure/monitoring/prometheus/rules/golden-signals.yaml
        infrastructure/monitoring/grafana/dashboards/golden-signals.json
        infrastructure/monitoring/grafana/dashboards/sre-overview.json
        infrastructure/monitoring/opentelemetry/otel-collector.yaml
        infrastructure/scripts/deploy/deploy.sh
        infrastructure/scripts/deploy/rollback.sh
        infrastructure/scripts/deploy/smoke-test.sh
        skills/README.md
        skills/sre/golden-signals.md
        skills/sre/prr.md
        skills/sre/cuj.md
        skills/ai/guardrails.md
        skills/privacy/pii.md
        skills/privacy/lgpd.md
        skills/privacy/gdpr.md
        skills/change-management/rfc-process.md
        skills/change-management/deploy-rollback.md

009  →  src/agents/hitl_gateway.py
        src/observability/otel_setup.py
        src/observability/metrics.py
        src/observability/logger.py
        src/shared/config.py
        src/shared/models.py
        src/guardrails/action_limits.py
        src/guardrails/audit_logger.py

010  →  src/guardrails/pii_filter.py          ← content policy rules apply
        src/guardrails/prompt_injection_guard.py  ← content policy rules apply
        tests/unit/guardrails/test_pii_filter.py
        tests/unit/guardrails/test_prompt_injection_guard.py
        tests/security/test_owasp_llm_top10.py
        tests/security/test_pii_leakage.py
        tests/chaos/runbooks/game-day-playbook.md

011  →  docs/postmortems/POSTMORTEM-TEMPLATE.md

012  →  (no files created — validation report only)
```

---

## Troubleshooting

| Symptom                               | Likely cause                              | Fix                                                                                |
| ------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------- |
| Content filtering block in prompt 010 | Guardrail or test content too specific    | Split 010: run `pii_filter.py` alone, then `prompt_injection_guard.py`, then tests |
| File already exists message           | Prompt was partially run before           | Safe to continue — existing files are skipped                                      |
| Missing directory error               | Prompt 001 was not run                    | Run 001 first, then retry the failed prompt                                        |
| ADR index inconsistency in prompt 012 | An ADR file was not created by prompt 003 | Re-run prompt 003; existing files will be skipped                                  |
| Validation reports missing `.gitkeep` | A new directory was added without one     | Add `.gitkeep` manually to the flagged directory                                   |

---

_Template version: 2.1.0 — Reference: `MONOREPO-STRUCTURE-EN.md`_
