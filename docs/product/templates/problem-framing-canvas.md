# Problem Framing Canvas — FEAT-{id}

> **Owner:** Product Owner | **Phase:** 1 (Conception) | **Status:** Draft | Under Review | Approved
> Copy this file to `docs/product/FEAT-{id}/problem-framing-canvas.md` and fill every field.
> When agent-generated, prepend the Agent-Disclosure Header (see `docs/product/README.md`).
>
> Purpose: force a problem to be understood and evidenced **before** any solution is specified.
> A canvas with empty or hand-waved fields is a signal the feature is not ready for discovery.

---

| Field                           | Answer                                                                        |
| ------------------------------- | ----------------------------------------------------------------------------- |
| **Customer segment**            | {which type of organisation/team buys or uses this}                           |
| **User persona**                | {who performs the job — link `personas.md`}                                   |
| **Buyer persona**               | {who authorises spend — may equal the user; link `personas.md`}               |
| **Problem statement**           | {the user/business problem, in their words — NOT the proposed build}          |
| **Current workaround**          | {what they do today instead — spreadsheet, manual step, competitor}           |
| **Pain intensity**              | {Critical / High / Medium / Low — and why}                                    |
| **Frequency**                   | {how often the pain occurs — per day/week/release}                            |
| **Business impact**             | {cost of the pain — time, money, risk, churn — quantified if possible}        |
| **Risk of doing nothing**       | {what happens if we ship nothing this quarter}                                |
| **Expected measurable outcome** | {the one metric that proves the problem is solved — see `success-metrics.md`} |
| **Evidence source**             | {interview, ticket volume, support data, analytics, market signal}            |
| **Confidence**                  | {High / Medium / Low — how strong is the evidence}                            |

---

## Out of scope

List what this feature explicitly will **not** address, to prevent scope creep:

- {non-goal 1}
- {non-goal 2}

## Open questions

- [ ] {question that must be resolved before specification}

---

## Related

- `docs/product/templates/personas.md` — user & buyer personas
- `docs/product/templates/value-hypothesis.md` — why we believe this is worth building
- `docs/product/templates/success-metrics.md` — how we will measure success
- `docs/process/DEFINITION_OF_READY.md` — gate this canvas feeds into
