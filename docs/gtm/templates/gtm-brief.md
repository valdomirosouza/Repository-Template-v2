# GTM Brief — {product / FEAT-id}

> **Owner:** Product Owner | **Status:** Draft | Under Review | Approved
> Copy to `docs/gtm/FEAT-{id}/gtm-brief.md`. When agent-generated, prepend the Agent-Disclosure
> Header (see `docs/product/README.md`). All pricing/packaging entries are **hypotheses** until
> validated with real buyers.

---

## 1. Ideal Customer Profile (ICP)

| Attribute            | Value                                                            |
| -------------------- | ---------------------------------------------------------------- |
| **Company type**     | {industry, regulated?, AI-maturity}                              |
| **Size**             | {team size / company size / revenue band}                        |
| **Trigger event**    | {what makes them start looking — e.g. "adopting agents in prod"} |
| **Must-have traits** | {what qualifies them in}                                         |
| **Disqualifiers**    | {what rules them out}                                            |

## 2. Buyer vs user

| Role               | Who             | Cares about             | Success metric       |
| ------------------ | --------------- | ----------------------- | -------------------- |
| **Economic buyer** | {title}         | {ROI, risk, compliance} | {board-level metric} |
| **Champion**       | {title}         | {their own win}         | {…}                  |
| **End user**       | {title}         | {daily job}             | {…}                  |
| **Blocker**        | {e.g. Security} | {what could veto}       | {…}                  |

(Link `docs/product/templates/personas.md` rather than re-deriving.)

## 3. Market

| Field                        | Value                                                  |
| ---------------------------- | ------------------------------------------------------ |
| **Market category**          | {the category buyers already shop in}                  |
| **Differentiation**          | {the one thing only we do well}                        |
| **Competitive alternatives** | {incl. "do nothing" / build-in-house / specific tools} |
| **Why now**                  | {market/tech shift that makes this timely}             |

## 4. Packaging & pricing (hypotheses)

| Field                | Hypothesis                                            |
| -------------------- | ----------------------------------------------------- |
| **Packaging**        | {free/OSS · team · enterprise · usage-based}          |
| **Pricing model**    | {per-seat / per-action / per-agent / flat}            |
| **Value metric**     | {the unit the price scales with — see unit economics} |
| **Price hypothesis** | {ballpark + rationale}                                |

## 5. Adoption

- **Adoption friction:** {what makes it hard to start — setup, trust, integration}
- **Onboarding path:** {first-value steps — link `adoption-plan.md`}
- **Expansion motion:** {how usage grows after first value}

## 6. Proof

- **Success story template:** {customer → problem → solution → measurable result}
- **Sales enablement notes:** {link `sales-enablement.md`}

---

## Related

- `docs/gtm/templates/positioning.md`
- `docs/gtm/templates/adoption-plan.md`
- `docs/product/templates/value-hypothesis.md`
- `specs/sre/finops.md` — unit economics inputs for the value metric
