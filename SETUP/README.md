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

| #   | File            | Topic                                                                  | Est. files created  | Risk level   |
| --- | --------------- | ---------------------------------------------------------------------- | ------------------- | ------------ |
| 1   | `001-prompt.md` | Directory scaffold + `.gitkeep` files                                  | ~55 dirs            | None         |
| 2   | `002-prompt.md` | Root governance files                                                  | 10 files            | None         |
| 3   | `003-prompt.md` | ADRs (0001–0015) + Glossary + Repo structure                           | 10 files            | None         |
| 4   | `004-prompt.md` | Privacy docs + AI Governance docs                                      | 9 files             | None         |
| 5   | `005-prompt.md` | SRE + Change Management + Runbooks (incl. RB-003)                      | 11 files            | None         |
| 6   | `006-prompt.md` | Specs (SDD)                                                            | 10 files            | None         |
| 7   | `007-prompt.md` | CI/CD workflows + Harness + chaos-schedule.yml                         | 15 files            | None         |
| 8   | `008-prompt.md` | Infrastructure monitoring + Skills + CUJ dashboards                    | 15 files            | None         |
| 9   | `009-prompt.md` | Source code: agents, observability, shared (base)                      | 7 files             | None         |
| 10  | `010-prompt.md` | Guardrails source + Security tests                                     | 8 files             | **Isolated** |
| 11  | `011-prompt.md` | Validation + Summary report                                            | 0 files (read-only) | None         |
| 12  | `012-prompt.md` | Postmortem template                                                    | 1 file              | None         |
| 13  | `013-prompt.md` | Resilience + persistence layer (retry, HITL store, feature flags, K8s) | 14 files            | None         |
| 14  | `014-prompt.md` | Security & resilience hardening v1.17.0 (Waves A–E)                    | 28 files            | None         |

**Total target:** ~198 files across ~85 directories.

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

After completing all 13 prompts, run prompt **011** to get a full validation report.
The report checks:

| Check                     | What is verified                                |
| ------------------------- | ----------------------------------------------- |
| Directory structure       | All required directories exist                  |
| File presence             | All ~170 required files exist                   |
| ADR index consistency     | Every ADR in the index (0001–0015) has a file   |
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

003  →  docs/adr/README.md                                   ← master index (ADR-0001 → ADR-0015)
        docs/adr/ADR-0001-monorepo-structure-and-governance.md
        docs/adr/ADR-0002-technology-stack-selection.md
        docs/adr/ADR-0003-async-api-strategy.md
        docs/adr/ADR-0004-observability-stack.md
        docs/adr/ADR-0005-message-broker-selection.md
        docs/adr/ADR-0006-deployment-strategy.md
        docs/adr/ADR-0007-service-mesh.md
        docs/adr/ADR-0008-secrets-management.md
        docs/adr/ADR-0009-caching-strategy.md
        docs/adr/ADR-0010-agent-framework-selection.md
        docs/adr/ADR-0011-hitl-hotl-model.md
        docs/adr/ADR-0012-pii-masking-strategy.md
        docs/adr/ADR-0013-data-retention-policy.md
        docs/adr/ADR-0014-multi-agent-harness-strategy.md
        docs/adr/ADR-0015-feature-flag-strategy.md           ← OpenFeature + flagd
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
        docs/runbooks/RB-003-hitl-recovery.md                ← HITL recovery runbook (PRR-OPS-002)

006  →  specs/README.md
        specs/system/vision.md
        specs/system/architecture.md
        specs/system/async-event-flow.md
        specs/ai/agent-design.md
        specs/ai/hitl-hotl.md
        specs/ai/guardrails.md
        specs/ai/harness-design.md                           ← multi-agent harness spec (ADR-0014)
        specs/privacy/pii-inventory.md
        specs/privacy/data-retention.md
        specs/privacy/dpia-ripd.md

007  →  .github/workflows/ci.yml
        .github/workflows/cd-staging.yml
        .github/workflows/cd-production.yml
        .github/workflows/sbom.yml
        .github/workflows/secret-scanning.yml
        .github/workflows/release.yml
        .github/workflows/chaos-schedule.yml                 ← nightly chaos experiments CI
        .github/pull_request_template.md
        .github/CODEOWNERS
        .github/ISSUE_TEMPLATE/change_request.md
        .github/ISSUE_TEMPLATE/bug_report.md
        harness/code-check.yml
        harness/staging-check.yml
        harness/release-check.yml
        harness/doc-check.yml

008  →  infrastructure/README.md                             ← infra overview + K8s probe reference
        infrastructure/monitoring/prometheus/rules/golden-signals.yaml
        infrastructure/monitoring/grafana/dashboards/golden-signals.json
        infrastructure/monitoring/grafana/dashboards/sre-overview.json
        infrastructure/monitoring/grafana/cuj-dashboards/CUJ-001-user-request-processing.json
        infrastructure/monitoring/opentelemetry/otel-collector.yaml
        infrastructure/scripts/deploy/deploy.sh
        infrastructure/scripts/deploy/rollback.sh
        infrastructure/scripts/deploy/smoke-test.sh
        skills/README.md
        skills/sre/golden-signals.md
        skills/sre/prr.md
        skills/sre/cuj.md
        skills/ai/guardrails.md
        skills/ai/harness.md                                 ← multi-agent harness skill (ADR-0014)
        skills/privacy/pii.md
        skills/privacy/lgpd.md
        skills/privacy/gdpr.md
        skills/change-management/rfc-process.md
        skills/change-management/deploy-rollback.md
        skills/observability/otel-instrumentation.md
        skills/api/rest-api-design.md
        skills/devsecops/secret-scanning.md
        skills/sdlc/spec-lifecycle.md

009  →  src/agents/hitl_gateway.py
        src/agents/orchestrator/orchestrator.py
        src/agents/harness/coordinator.py
        src/agents/harness/planner.py
        src/agents/harness/evaluator.py
        src/agents/harness/context_manager.py
        src/agents/harness/models.py
        src/observability/otel_setup.py
        src/observability/metrics.py
        src/observability/logger.py
        src/shared/config.py
        src/shared/models.py
        src/shared/llm_client.py
        src/guardrails/action_limits.py
        src/guardrails/audit_logger.py

010  →  src/guardrails/pii_filter.py               ← content policy rules apply
        src/guardrails/prompt_injection_guard.py    ← content policy rules apply
        tests/unit/guardrails/test_pii_filter.py
        tests/unit/guardrails/test_prompt_injection_guard.py
        tests/security/test_owasp_llm_top10.py
        tests/security/test_pii_leakage.py
        tests/chaos/runbooks/game-day-playbook.md

011  →  (no files created — validation report only)

012  →  docs/postmortems/POSTMORTEM-TEMPLATE.md

013  →  src/shared/retry.py                         ← with_retry() + CircuitBreaker (ADR-0014)
        src/shared/db_client.py                     ← ResilientDBPool (asyncpg + CB + retry)
        src/shared/feature_flags.py                 ← OpenFeature SDK wrapper (ADR-0015)
        src/api/rest/_limiter.py                    ← slowapi Limiter singleton
        src/agents/hitl_store.py                    ← HITLStore Protocol + InMemory + Redis impls
        infrastructure/k8s/deployment.yaml          ← all three probes + preStop + secretKeyRef
        infrastructure/k8s/service.yaml
        infrastructure/k8s/hpa.yaml                 ← CPU + agent_semaphore_waiting + kafka_consumer_lag
        infrastructure/k8s/pdb.yaml                 ← minAvailable: 2
        infrastructure/k8s/prometheus-adapter-config.yaml
        infrastructure/feature-flags/README.md
        infrastructure/feature-flags/flagd.yaml     ← k8s Deployment + Service + ConfigMap
        infrastructure/feature-flags/flags/autonomous-mode.yaml
        alembic.ini
        alembic/env.py
        alembic/versions/0001_create_audit_events.py
        tests/integration/test_hitl_redis_store.py
        tests/chaos/experiments/kill-agent.yaml
        tests/chaos/experiments/broker-outage.yaml
        tests/chaos/experiments/network-partition.yaml

014  →  src/workers/__init__.py
        src/workers/request_consumer.py             ← DLQ + safe offset commit (REM-012, REM-013)
        src/api/rest/auth.py                        ← HITL operator JWT auth (REM-001)
        src/api/rest/security_headers.py            ← HTTP security headers middleware
        docs/adr/ADR-0016-agent-sandbox-execution-policy.md
        docs/adr/ADR-0017-agent-memory-architecture.md
        docs/adr/ADR-0018-db-encryption-at-rest.md
        docs/adr/ADR-0019-redis-tls-value-encryption.md
        docs/adr/ADR-0020-finops-cost-allocation.md
        docs/adr/ADR-0021-agent-communication-protocol.md
        docs/adr/ADR-0022-testing-strategy.md
        docs/adr/ADR-0023-frontend-architecture.md
        docs/adr/ADR-0024-api-versioning-strategy.md
        docs/adr/ADR-0025-language-selection.md
        docs/compliance/README.md
        docs/compliance/hardening-plan.md
        docs/compliance/remediation-register.md
        docs/compliance/iso27001-annex-a-control-matrix.md
        docs/compliance/soc2-tsc-mapping.md
        docs/compliance/slsa-supply-chain-assessment.md
        docs/compliance/trust-summary.md
        docs/compliance/security-questionnaire-quickref.md
        docs/governance/owner-onboarding.md
        docs/sre/runbooks/dlq-accumulating.md
        docs/sre/runbooks/redis-ha.md
        docs/sre/runbooks/db-key-rotation.md
        infrastructure/k8s/network-policies/README.md
        infrastructure/k8s/network-policies/default-deny-ingress.yaml
        infrastructure/k8s/network-policies/api-gateway.yaml
        infrastructure/k8s/network-policies/monitoring.yaml
        infrastructure/k8s/network-policies/istio-peer-auth.yaml
        infrastructure/monitoring/alertmanager/alertmanager.yml
        .github/workflows/codeql.yml
        .github/workflows/pr-governance.yml
        .trivyignore
```

---

## Troubleshooting

| Symptom                               | Likely cause                              | Fix                                                                                |
| ------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------- |
| Content filtering block in prompt 010 | Guardrail or test content too specific    | Split 010: run `pii_filter.py` alone, then `prompt_injection_guard.py`, then tests |
| File already exists message           | Prompt was partially run before           | Safe to continue — existing files are skipped                                      |
| Missing directory error               | Prompt 001 was not run                    | Run 001 first, then retry the failed prompt                                        |
| ADR index inconsistency in prompt 011 | An ADR file was not created by prompt 003 | Re-run prompt 003; existing files will be skipped                                  |
| Validation reports missing `.gitkeep` | A new directory was added without one     | Add `.gitkeep` manually to the flagged directory                                   |

---

_Template version: 2.3.0 — Reference: `MONOREPO-STRUCTURE-EN.md`_
