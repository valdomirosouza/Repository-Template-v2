---
name: Change Request
description: Propose a change to the system — feature, enhancement, or architectural update
labels: ["change-request", "needs-triage"]
assignees: []
---

## Problem Description / Motivation

<!-- What problem does this change solve? Why is it needed? -->

## Referenced Spec

<!-- Path to the governing spec — REQUIRED for all change types. Write the spec first if it does not exist. -->
<!-- e.g. specs/ai/guardrails.md · specs/system/architecture.md · specs/api/rest-api-design.md -->
<!-- No implementation may begin without a spec (CLAUDE.md §3.4). -->

## Change Type

- [ ] **Standard** — minor enhancement or bug fix; no CAB review required
- [ ] **Normal** — significant change; requires RFC and CAB approval before implementation
- [ ] **Emergency** — critical fix in production; CAB notified post-merge; RFC within 24 h

## Estimated Impact

| Dimension           | Description                                   |
| ------------------- | --------------------------------------------- |
| Services affected   | <!-- e.g. agent-service, api-gateway -->      |
| Data flows affected | <!-- e.g. domain.created event, HITL flow --> |
| Downtime expected   | <!-- None / Rolling / Maintenance window -->  |
| Rollback time       | <!-- Estimated time to rollback if needed --> |

## Acceptance Criteria

```
Given  <!-- initial system state -->
When   <!-- action or event -->
Then   <!-- expected observable outcome -->
```

## Rollback Plan

<!-- How to revert this change if it causes issues after deployment -->

## Privacy Impact

- [ ] This change introduces or modifies personal data processing
  - [ ] DPIA/RIPD updated and DPO approved before implementation
  - DPIA/RIPD reference: `docs/privacy/dpia/dpia-v?.md`

## Security Considerations

<!-- Any security implications? New attack surface, permission changes, new external calls? -->

## Step 2 — Validation Checklist

Before starting implementation, the implementer must confirm:

- [ ] Spec read and implementation will align with it
- [ ] ADRs reviewed for binding constraints (`docs/adr/`)
- [ ] Relevant skills loaded per CLAUDE.md §4
- [ ] Glossary terms confirmed (`docs/glossary.md`)
- [ ] No rule violations identified (CLAUDE.md §3 — privacy, security, AI governance, architecture)
- [ ] DPIA/RIPD flagged if this change introduces new personal data processing (CLAUDE.md §3.1)

## Step 3 — Implementation Plan

<!-- High-level steps to implement this change — REQUIRED before writing any code (CLAUDE.md §2 Step 3) -->
<!-- Share this plan and confirm alignment before starting implementation. -->

1.
2.
3.

## Definition of Done

- [ ] Spec created or updated and approved
- [ ] Implementation complete and tests passing (coverage ≥ 80%)
- [ ] CHANGELOG.md updated
- [ ] ADR filed if architectural decision made
- [ ] PRR completed (for production deployments)
- [ ] RFC approved by CAB (for Normal changes)
