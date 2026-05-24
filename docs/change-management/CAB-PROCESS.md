# Change Advisory Board (CAB) Process

**Owner:** Tech Lead | **Last reviewed:** 2026-05-24

---

## CAB Composition

| Role               | Member   | Mandatory for                            |
| ------------------ | -------- | ---------------------------------------- |
| Tech Lead          | \<Name\> | All changes                              |
| Security Lead      | \<Name\> | All changes                              |
| SRE Lead           | \<Name\> | Infrastructure and reliability changes   |
| DPO                | \<Name\> | Changes affecting PII processing         |
| AI Governance Lead | \<Name\> | Changes to agent behaviour or guardrails |
| Product Owner      | \<Name\> | Changes affecting user-facing behaviour  |

A quorum requires Tech Lead + Security Lead + at least one other member.

---

## Meeting Cadence

| Type          | Frequency                  | Format               |
| ------------- | -------------------------- | -------------------- |
| Standard CAB  | Weekly (Tuesday 14:00 UTC) | Synchronous — 30 min |
| Emergency CAB | On-demand — within 4 hours | Async (Slack thread) |

---

## Submission Requirements

### Normal Changes

- RFC filed in `docs/change-management/rfc/RFC-NNNN-<title>.md` using `RFC-TEMPLATE.md`
- RFC submitted to Tech Lead at least **48 hours** before the CAB meeting
- RFC includes: implementation plan, rollback plan, testing plan, privacy impact, security impact
- All required reviewers (Tech Lead, Security Lead) have provided feedback before CAB

### Emergency Changes

- Tech Lead notified immediately via incident channel
- Abbreviated RFC filed async (full RFC within 24 hours post-fix)
- TL + SecOps approval obtained async within 4 hours
- Deploy may proceed after async approval; CAB ratifies at next weekly meeting

---

## Decision Options

| Decision                    | Meaning                                                              | Next step                                                   |
| --------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Approve**                 | RFC is approved as submitted; deploy may proceed after CI gates pass | Merge PR; deploy per RFC plan                               |
| **Approve with conditions** | Approved subject to specified changes                                | Author addresses conditions; re-submit for TL sign-off only |
| **Defer**                   | More information needed; not enough to decide                        | Author provides additional information; re-submit next CAB  |
| **Reject**                  | RFC is not approved                                                  | Author may revise approach and re-submit as a new RFC       |

---

## CAB Meeting Template

```
## CAB Meeting — YYYY-MM-DD

### Attendees
- [ ] Tech Lead
- [ ] Security Lead
- [ ] SRE Lead
- [ ] DPO (if required)
- [ ] AI Governance Lead (if required)

### RFCs Under Review

#### RFC-NNNN — <Title>
- Author:
- Summary:
- Key risks:
- Decision: Approve / Approve with conditions / Defer / Reject
- Conditions (if any):
- Decision rationale:

### Decision Log
| RFC | Decision | Conditions | Decided by | Date |
|-----|----------|-----------|-----------|------|
| RFC-NNNN | | | | |
```

---

## Emergency Change Process

```
1. Incident detected → on-call engineer assesses severity
2. Tech Lead notified via incident channel
3. Emergency branch created: hotfix/SPEC-NNN-<description>
4. Abbreviated RFC filed async (key sections only)
5. TL approval obtained via Slack/async (document in RFC)
6. SecOps approval obtained via Slack/async (document in RFC)
7. PR opened with expedited review (TL as mandatory reviewer)
8. Deploy via rollback-safe method (prefer blue-green for emergencies)
9. Post-mortem within 48 hours
10. Full RFC completed and ratified at next weekly CAB
```

---

## Appeals Process

If an RFC is rejected and the author believes the decision was incorrect:

1. Author documents the disagreement in writing and sends to Engineering Manager
2. Engineering Manager reviews RFC, CAB decision, and conditions within 5 business days
3. Engineering Manager may: uphold rejection, request CAB reconsideration, or escalate to CTO
4. Decision is final after Engineering Manager review
