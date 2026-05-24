---
name: Change Request
description: Propose a change to the system — feature, enhancement, or architectural update
labels: ["change-request", "needs-triage"]
assignees: []
---

## Problem Description / Motivation

<!-- What problem does this change solve? Why is it needed? -->

## Referenced Spec

<!-- Path to the governing spec. Required for Normal and Emergency changes. -->
<!-- e.g. specs/ai/guardrails.md -->

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

## Definition of Done

- [ ] Spec created or updated and approved
- [ ] Implementation complete and tests passing (coverage ≥ 80%)
- [ ] CHANGELOG.md updated
- [ ] ADR filed if architectural decision made
- [ ] PRR completed (for production deployments)
- [ ] RFC approved by CAB (for Normal changes)
