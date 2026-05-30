## Summary

<!-- One paragraph description of the change and its purpose -->

## Workflow Compliance (CLAUDE.md §2)

_Confirm that the mandatory 7-step cycle was followed before code was written:_

- [ ] **Step 1 — Registered:** Issue filed and linked below; spec exists in `specs/` before coding started
- [ ] **Step 2 — Validated:** Rules (§3), relevant Skills (§4), and ADRs (`docs/adr/`) reviewed; no violations found
- [ ] **Step 3 — Planned:** Implementation plan documented in the issue before coding started

## Linked Issue

Closes #<!-- issue number -->

## Referenced Spec

<!-- Path to the spec governing this change, e.g. specs/ai/guardrails.md -->
<!-- REQUIRED: No PR may be merged without a spec reference (see specs/README.md) -->

## Impacted ADRs

<!-- List any ADRs this change relates to, supersedes, or is governed by -->
<!-- e.g. ADR-0011 (HITL/HOTL), ADR-0012 (PII Masking) -->

## Change Type

- [ ] Standard — minor enhancement or bug fix; no RFC required
- [ ] Normal — requires RFC and CAB review before merge
- [ ] Emergency — hotfix; RFC must be filed within 24 h after merge

## Deploy Command

```bash
# Python:   make deploy-staging SERVICE=api-gateway VERSION=x.y.z
# Java:     make deploy-staging SERVICE=domain-service VERSION=x.y.z
# Go:       make deploy-staging SERVICE=event-worker VERSION=x.y.z
```

## Rollback Plan

<!-- How to revert this change if it causes issues in production -->
<!-- e.g. make rollback / helm rollback <service> --namespace production / feature flag off -->

## Privacy Impact

- [ ] This change introduces or modifies personal data processing
  - If yes, DPIA/RIPD reference: `docs/privacy/dpia/dpia-v?.md`
  - If yes, confirm DPIA/RIPD is approved by DPO before merge

## PR Checklist

- [ ] Tests written and passing — coverage ≥ 80%
  - Python: `make test-unit-python` · Java: `make test-unit-java SERVICE=<name>` · Go: `make test-unit-go SERVICE=<name>` · Frontend: `make test-unit-frontend`
- [ ] No secrets or real PII in any changed file
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Spec updated if implementation diverged from it
- [ ] ADR filed if a new architectural decision was made
- [ ] `services.yaml` updated if a new service, port, or Kafka topic was added
- [ ] Privacy: guardrails unmodified or strengthened (never weakened)
- [ ] _(AI Agents Module only)_ HITL gateway used for any new agent action with real-world effects
- [ ] `CODEOWNERS` reviewers have approved (auto-requested)

> CI runs the same gates defined in `harness/code-check.yml` (lint, unit tests ≥ 80%, SAST, secret scan, PII scan). All blocking gates must pass before merge.
