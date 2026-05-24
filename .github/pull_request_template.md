## Summary

<!-- One paragraph description of the change and its purpose -->

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
# e.g. make deploy-staging VERSION=x.y.z
```

## Rollback Plan

<!-- How to revert this change if it causes issues in production -->
<!-- e.g. helm rollback app --namespace production / feature flag off -->

## Privacy Impact

- [ ] This change introduces or modifies personal data processing
  - If yes, DPIA/RIPD reference: `docs/privacy/dpia/dpia-v?.md`
  - If yes, confirm DPIA/RIPD is approved by DPO before merge

## PR Checklist

- [ ] Tests written and passing (`make test`) — coverage ≥ 80%
- [ ] No secrets or real PII in any changed file
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Spec updated if implementation diverged from it
- [ ] ADR filed if a new architectural decision was made
- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] HITL gateway used for any new agent action with real-world effects
- [ ] `CODEOWNERS` reviewers have approved (auto-requested)
