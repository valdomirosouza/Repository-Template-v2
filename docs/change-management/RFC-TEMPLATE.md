# RFC-NNNN — \<Title\>

**RFC Number:** RFC-NNNN
**Title:** \<Descriptive title\>
**Author:** \<Name\>
**Date:** YYYY-MM-DD
**Status:** Draft | Under Review | Approved | Rejected | Withdrawn

---

## Summary

One paragraph describing the change, what it does, and why it is needed.

---

## Motivation

Why is this change needed? What problem does it solve? What happens if we don't
make this change? Link to the GitHub Issue that initiated this RFC.

**GitHub Issue:** #\<number\>
**Referenced Spec:** `specs/<path>`

---

## Affected Components

| Component          | Change type               | Impact          |
| ------------------ | ------------------------- | --------------- |
| \<service/module\> | \<Add / Modify / Remove\> | \<Description\> |

---

## Change Type

- [ ] Normal (CAB review required — submit 48h before meeting)
- [ ] Emergency (TL + SecOps async approval — post-mortem within 48h)

---

## Estimated Impact

| Dimension               | Assessment             |
| ----------------------- | ---------------------- |
| Affected services       | \<List\>               |
| Affected users          | \<Estimate or "None"\> |
| Expected downtime       | \<Duration or "None"\> |
| Data migration required | Yes / No               |
| Rollback complexity     | Low / Medium / High    |

---

## Implementation Plan

| Step | Description          | Owner    | Duration     |
| ---- | -------------------- | -------- | ------------ |
| 1    | \<Step description\> | \<Name\> | \<Estimate\> |
| 2    |                      |          |              |

---

## Rollback Plan

How to revert this change if it causes issues in production.

**RTO target:** \<Duration — from `docs/sre/slo/slo.yaml`\>

Steps:

1. \<Rollback step 1\>
2. \<Rollback step 2\>

Rollback command:

```bash
bash infrastructure/scripts/deploy/rollback.sh --env=production --service=<name>
```

---

## Testing Plan

| Test type   | What is tested | Pass criteria |
| ----------- | -------------- | ------------- |
| Unit        |                |               |
| Integration |                |               |
| Smoke       |                |               |
| Performance |                |               |

---

## Privacy Impact

- [ ] This change introduces or modifies personal data processing

If yes:

- New/changed data categories: \<List\>
- DPIA review required: Yes / No
- DPIA reference: `docs/privacy/dpia/dpia-vN.md`
- RIPD reference: `docs/privacy/ripd/ripd-vN.md`
- DPO notified: Yes / No / Not applicable

---

## Security Impact

- [ ] This change affects the attack surface or security controls

If yes:

- Security review reference: \<PR / ticket\>
- Guardrails affected: \<List files in `src/guardrails/`\>
- Threat model updated: Yes / No

---

## Acceptance Criteria

```gherkin
Given <precondition>
When <action>
Then <expected outcome>
```

---

## Approvals

| Role          | Name | Decision           | Date | Notes                      |
| ------------- | ---- | ------------------ | ---- | -------------------------- |
| Tech Lead     |      | ☐ Approve ☐ Reject |      |                            |
| Security Lead |      | ☐ Approve ☐ Reject |      |                            |
| DPO           |      | ☐ Approve ☐ Reject |      | Required if privacy impact |
| CAB           |      | ☐ Approve ☐ Reject |      |                            |

---

## Version History

| Version | Date     | Author     | Changes       |
| ------- | -------- | ---------- | ------------- |
| 0.1     | \<Date\> | \<Author\> | Initial draft |
