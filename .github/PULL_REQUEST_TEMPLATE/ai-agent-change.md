<!-- AI/agent change (src/agents, src/guardrails, action types, autonomy). ?template=ai-agent-change.md -->

## Summary

<!-- What changed in the AI/agent surface and why. -->

## Linked issue / spec

Closes #
Spec: <!-- SPEC-NNN --> · AI safety: `docs/ai-governance/ai-safety-checklist.md`

## HITL / HOTL impact

- [ ] No change to HITL gateway / autonomy, OR change is described below
- [ ] Autonomy level / feature flags unchanged (or governance sign-off referenced: ADR-0015)

## Tool-permission changes

- [ ] New/changed tools registered in `infrastructure/agent-tools/tools.yaml` with risk/HITL/reversibility
- [ ] No permissions granted beyond `specs/ai/guardrails.md`

## Tests

- [ ] Prompt-injection tests pass (`tests/abuse_cases/ -m abuse_case`) — count not reduced
- [ ] Data-leakage / PII tests pass (`tests/security/`)
- [ ] Model-contract tests run if model version changed (`tests/model_contract/`)

## Guardrails & review

- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] AI Safety & Agent Governance checklist completed and attached
- [ ] AI Governance Lead review requested
