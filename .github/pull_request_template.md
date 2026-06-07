<!--
Tip: for a lighter, change-type-specific template, append a query string to the PR URL:
  ?expand=1&template=docs.md | standard-change.md | ai-agent-change.md
                            | security-change.md | infrastructure-change.md
See the change-type table in CONTRIBUTING.md. This default is the full enterprise checklist.
-->

## Summary

<!-- One paragraph description of the change and its purpose -->

## Workflow Compliance (CLAUDE.md §2)

_Confirm the mandatory 10-step SDD cycle was followed before code was written:_

- [ ] **Step 1 — Spec read:** Relevant spec in `specs/` read before coding started; spec exists or was written first
- [ ] **Step 2 — ADRs read:** Relevant ADRs in `docs/adr/` reviewed; no architectural violations
- [ ] **Step 3 — Glossary checked:** All terms verified against `docs/glossary.md`
- [ ] **Step 4 — Issue exists:** GitHub Issue filed and linked below; spec referenced in issue
- [ ] **Step 5 — Privacy checked:** DPIA/RIPD review flagged if new PII processing introduced
- [ ] **Step 6 — Implemented:** Code follows spec; no gold-plating or scope creep
- [ ] **Step 7 — Tests written:** Unit coverage ≥ 80%; integration tests for service boundaries
- [ ] **Step 8 — Guardrails run:** `pii_filter`, `prompt_injection_guard`, `audit_logger` verified
- [ ] **Step 9 — ADR updated:** New ADR filed if an architectural decision was made
- [ ] **Step 10 — CHANGELOG updated:** Entry added under `[Unreleased]`

## Linked Issue

Closes #<!-- issue number -->

## Referenced Spec

<!-- Path to the spec governing this change, e.g. specs/api/rest-api-design.md -->
<!-- REQUIRED for feat/fix/security/privacy/perf PRs (no-spec label to exempt) -->

## Impacted ADRs

<!-- ADRs this change relates to, supersedes, or is governed by -->
<!-- e.g. ADR-0027 (ISO 27001 CM), ADR-0028 (DORA) -->

## Change Type (ISO 27001 — CLAUDE.md §11)

- [ ] `standard-change` — pre-approved, low-risk; no RFC required; deploy window Mon–Thu 10:00–17:00
- [ ] `normal-change` — RFC approved by CAB before merge; RFC_ID: `RFC-`<!-- number -->
- [ ] `emergency-change` — TL + SecOps async approval; retroactive RFC within 24 h; post-mortem required

## Deploy & Rollback

```bash
# Deploy to staging
make deploy-staging SERVICE=<name> VERSION=x.y.z

# Rollback (if needed)
make rollback SERVICE=<name>
```

Rollback plan: <!-- describe or reference runbook -->

## Privacy Impact

- [ ] This change introduces or modifies personal data processing
  - DPIA/RIPD reference: `docs/privacy/dpia/dpia-v?.md`
  - DPO approval confirmed before merge

## PR Checklist

### Core

- [ ] Tests written and passing — coverage ≥ 80%
- [ ] No secrets or real PII in any changed file
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Spec updated if implementation diverged from it
- [ ] ADR filed if a new architectural decision was made
- [ ] `services.yaml` updated if a new service, port, or Kafka topic was added
- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] `CODEOWNERS` reviewers approved (auto-requested)
- [ ] _(AI Agents Module only)_ HITL gateway used for any new agent action with real-world effects

### AI Safety & Agent Governance (Phase 10 — required for AI/LLM/agentic changes)

_Only when this PR touches `src/agents/`, `src/guardrails/`, a new `action_type`, or autonomy. Otherwise mark N/A._

- [ ] N/A — this PR is not an AI/LLM/agentic change
- [ ] AI Safety & Agent Governance checklist completed ([`docs/ai-governance/ai-safety-checklist.md`](../docs/ai-governance/ai-safety-checklist.md))
- [ ] Prompt-injection + data-leakage tests cover the change (`tests/abuse_cases/`, `tests/security/`, `tests/model_contract/`)
- [ ] Tool permissions reviewed in `infrastructure/agent-tools/tools.yaml`; AI Governance Lead approval obtained

### Compliance Gates (CLAUDE.md §7)

- [ ] **[IF SOX APPLIES]** RFC_ID present in commit for `normal-change` / `emergency-change`
- [ ] **[IF SOX APPLIES]** Financial data write paths produce audit records (`make test-security-python`)
- [ ] ISO 27001: change type label applied above (one of `standard-change` / `normal-change` / `emergency-change`)
- [ ] ISO 27001: deploy-rollback skill followed; rollback tested in staging before production
- [ ] DORA: lead time from first commit ≤ 24 h, or exception documented
- [ ] OWASP: DAST (ZAP) scan passed in staging — link report: <!-- docs/security/zap-reports/YYYY-MM-DD.html -->
- [ ] OWASP: no new CRITICAL/HIGH SAST or SCA findings without documented risk acceptance
- [ ] DevSecOps: container scan (Trivy) passed — zero CRITICAL CVEs
- [ ] DevSecOps: IaC scan (Checkov) passed on any `infrastructure/` changes
- [ ] DevSecOps: SBOM generated and signed (cosign attestation present)

> CI gates defined in `harness/code-check.yml` (lint, unit tests ≥ 80%, SAST, secret scan, PII scan, ISO-CM-01/02, OWASP-A03/A08/A09, DSEC-01–03, DORA-01) must all pass before merge.
