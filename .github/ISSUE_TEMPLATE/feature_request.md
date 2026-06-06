---
name: Feature Request
description: Propose a new feature or enhancement
labels: ["type: feature", "status: discovery"]
assignees: []
---

## Summary

<!-- One paragraph: what the feature does and why it is needed -->

## Problem / Opportunity

<!-- What user or business problem does this solve? -->
<!-- e.g. Operators cannot bulk-approve HITL requests, forcing them to click through each one individually -->

## Value Hypothesis (Phase 0 — Intake)

<!-- One line: the expected user/business value and how we'll know it worked. -->
<!-- e.g. "Bulk approval cuts operator review time ~40%; measured via PR/HITL review-time metric." -->

## Risk Class (Phase 0 — Intake)

<!-- Selects which downstream gates apply (risk-based flow, ADR-0058). Pick one: -->

- [ ] Small bug fix — Issue → PR → CI/security → deploy → observe
- [ ] Normal feature — Discovery → Spec → Dev → Review → Test → Release
- [ ] High-risk feature — full lifecycle + architecture/security/observability/release gates
- [ ] AI / LLM / agentic feature — full lifecycle + **AI Safety & Agent Governance** gate (Phase 10)
- [ ] Security-sensitive — full lifecycle + threat model + stricter approval/auditability
- [ ] Infrastructure / platform — full lifecycle + rollback plan + PRR

## Discovery Link

<!-- Link to docs/product/FEAT-{id}/discovery.md once the Discovery Primer is created (Phase 1).
     Leave blank until the agent generates it. -->

`docs/product/FEAT-` <!-- id --> `/discovery.md` — _pending_

## Size Estimate

<!-- S = 1–2 days · M = 3–5 days · L = 1–2 weeks · XL = > 2 weeks -->

- [ ] S
- [ ] M
- [ ] L
- [ ] XL

## Proposed Solution

<!-- High-level description of the intended implementation -->
<!-- Do NOT write code here — a spec must be written before implementation begins (CLAUDE.md §2 Step 1) -->

## Referenced Spec

<!-- Path to the spec governing this feature — REQUIRED before implementation starts -->
<!-- If no spec exists yet, create one under specs/ and link it here -->
<!-- e.g. specs/api/rest-api-design.md · specs/ai/guardrails.md -->

## Affected Services / Components

<!-- List the services, layers, or modules this feature touches -->
<!-- e.g. api-gateway (src/api/rest/), agent-service (src/agents/), frontend (frontend/) -->

## Impacted ADRs

<!-- ADRs that govern or constrain this feature -->
<!-- e.g. ADR-0011 (HITL/HOTL), ADR-0027 (ISO 27001 CM) -->

## Alternatives Considered

<!-- What other approaches were considered and why they were rejected -->

## Acceptance Criteria

<!-- Bullet list of observable, testable conditions that confirm the feature is complete -->

- [ ]
- [ ]
- [ ]

## Privacy Impact

- [ ] This feature introduces or modifies personal data processing
  - If yes, DPIA/RIPD review required before implementation (CLAUDE.md §2 Step 5)
  - DPIA/RIPD reference: `docs/privacy/dpia/dpia-v?.md`

## Change Type (ISO 27001 — CLAUDE.md §11)

- [ ] `standard-change` — low-risk, pre-approved pattern
- [ ] `normal-change` — requires RFC and CAB approval before merge; RFC_ID: `RFC-`<!-- number -->
- [ ] `emergency-change` — not applicable for feature requests

## Step 2 — Pre-Implementation Checklist

Before writing any code, the implementer must confirm:

- [ ] Spec written and linked above
- [ ] ADRs reviewed for binding constraints (`docs/adr/`)
- [ ] Relevant skills loaded (CLAUDE.md §4)
- [ ] GitHub Issue linked in the PR body (`Closes #<n>`)
- [ ] DPIA/RIPD flagged if new PII processing is introduced (CLAUDE.md §3.1)
- [ ] Threat model updated if new attack surface introduced (`specs/security/threat-model.md`)

## Definition of Done

- [ ] Spec updated if implementation diverged from it
- [ ] Unit tests written, coverage ≥ 80%
- [ ] Integration tests added for any new service boundary
- [ ] `CHANGELOG.md` updated under `Added`
- [ ] ADR filed if a new architectural decision was made
- [ ] `services.yaml` updated if a new service, port, or Kafka topic was added
- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] _(AI Agents Module only)_ HITL gateway used for any new agent action with real-world effects

## Definition of Ready Checklist

_This Issue may not enter a sprint until ALL items are checked (see `docs/process/DEFINITION_OF_READY.md`)._

- [ ] Problem statement written and linked to discovery doc (`docs/product/FEAT-{id}/discovery.md`)
- [ ] NFR doc created and approved by Security Lead — or "N/A: no new PII surface" stated explicitly
- [ ] Acceptance criteria written in Gherkin format and reviewed by Product Owner
- [ ] Feature spec template created (`specs/features/FEAT-{id}/feature-spec.md`) — sections 1–5 complete
- [ ] Size label applied (S / M / L / XL)
- [ ] Component labels applied (`component: api` / `frontend` / `infra` / `agent`)
- [ ] Tech Lead has commented on this Issue
- [ ] No unresolved blocking dependencies on other open Issues

## Additional Context

<!-- Mockups, related issues, Grafana dashboards, external references, etc. -->
