# Value Hypothesis — FEAT-{id}

> **Owner:** Product Owner | **Phase:** 2 (Discovery) | **Status:** Draft | Under Review | Approved
> Copy to `docs/product/FEAT-{id}/value-hypothesis.md`. When agent-generated, prepend the
> Agent-Disclosure Header (see `docs/product/README.md`).
>
> A value hypothesis is a falsifiable bet, not a feature description. State it so that data can
> later prove it true or false.

---

## Hypothesis statement

> We believe that **{building this capability}**
> for **{persona / segment}**
> will achieve **{measurable outcome}**.
> We will know we are right when we see **{signal / metric threshold}**
> within **{timeframe}**.

## Assumptions (riskiest first)

| #   | Assumption                               | If false…         | How we de-risk it           |
| --- | ---------------------------------------- | ----------------- | --------------------------- |
| A1  | {users actually have this problem}       | {feature unused}  | {interviews / spike / beta} |
| A2  | {they will change behaviour to adopt it} | {low adoption}    | {prototype test}            |
| A3  | {the outcome is attributable to this}    | {can't prove ROI} | {instrumentation / A-B}     |

## Leap-of-faith / kill criteria

- **Proceed if:** {evidence that justifies full build}
- **Pivot if:** {ambiguous signal}
- **Kill if:** {evidence the bet is wrong — e.g. < X% of beta users complete the journey}

## Validation method

{spike · prototype · concierge MVP · A-B test · beta cohort} — and the sample size / duration that
would make the result credible.

---

## Related

- `docs/product/templates/problem-framing-canvas.md`
- `docs/product/templates/success-metrics.md` — the metrics that test this hypothesis
- `docs/gtm/templates/gtm-brief.md`
