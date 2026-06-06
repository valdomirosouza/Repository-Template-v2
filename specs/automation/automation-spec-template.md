# Automation Spec: <Short Name>

> Copy this template. Fill in every section. Submit as a GitHub Issue with label
> `automation-request`. An engineer will review and Claude Code will scaffold the
> implementation. No coding required on your part.

**Status:** Draft | **Owner:** <Your name, role> | **Last updated:** YYYY-MM-DD
**Reviewer (engineer):** <Assigned engineer>
**Issue:** #<GitHub issue number>

---

## Trigger

_What starts this automation? Choose one:_

- [ ] **Scheduled** — runs at a fixed time: `<cron expression or plain English, e.g. "every Monday at 08:00">`
- [ ] **Event-driven** — triggered by: `<file upload / form submission / webhook / API call>`
- [ ] **Manual** — run on demand by: `<role or team>`

---

## Input

_What data does the automation need? Where does it come from?_

| Field | Source | Format | Contains PII? |
| ----- | ------ | ------ | ------------- |
|       |        |        | Yes / No      |
|       |        |        | Yes / No      |

_If PII is present (names, emails, IDs, phone numbers), the engineering reviewer
will apply masking before any logging or output sharing._

---

## Steps

_Numbered list of what the automation does, in plain language. No code._

1.
2.
3.

---

## Output

_What does the automation produce? Where does it go?_

| Output | Destination | Format | Visible to |
| ------ | ----------- | ------ | ---------- |
|        |             |        |            |

---

## Guardrails

_Answer each question. "Yes" answers require additional engineering controls._

| Question                                                   | Answer   | Notes |
| ---------------------------------------------------------- | -------- | ----- |
| Does it process personal data (names, emails, IDs)?        | Yes / No |       |
| Does it make external API calls or send notifications?     | Yes / No |       |
| Does it write to a database or shared file system?         | Yes / No |       |
| Does it run with elevated permissions or service accounts? | Yes / No |       |
| Could it cause irreversible effects if it runs twice?      | Yes / No |       |

---

## Rollback Procedure

_How do we undo the automation's output if something goes wrong?_

> Example: "Delete the generated report file. Re-run the previous week's report manually."

---

## SLA

| Property                    | Value                           |
| --------------------------- | ------------------------------- |
| Maximum run time            | e.g. 5 minutes                  |
| Run frequency               | e.g. weekly / daily / on-demand |
| Acceptable failure rate     | e.g. < 1% of runs               |
| On-call contact if it fails | <Name or team>                  |

---

## Approval Before Production

_Who must approve before the automation runs in production for the first time?_

- [ ] Owner (you): confirms the spec is complete and accurate
- [ ] Engineer reviewer: confirms implementation matches the spec
- [ ] HITL gate: `<required / not required>` — required if the automation has external effects

---

## Notes / Open Questions

_Anything the engineering team should know? Constraints, edge cases, known exceptions._

---

_Template version: 1.0 | `specs/automation/automation-spec-template.md` | Issue #11_
