# Adoption Plan — {product / FEAT-id}

> **Owner:** Product Owner | **Status:** Draft | Under Review | Approved
> Copy to `docs/gtm/FEAT-{id}/adoption-plan.md`. When agent-generated, prepend the Agent-Disclosure
> Header (see `docs/product/README.md`).
>
> Maps the journey from "never heard of it" to "expanding usage", with the friction and the
> measurable milestone at each stage. Target: a new user reaches **first value in under one hour**
> (the "golden path" — Theme 3 of the improvement plan).

---

## Adoption funnel

| Stage           | User goal                      | Friction to remove      | Activation milestone (measurable)    |
| --------------- | ------------------------------ | ----------------------- | ------------------------------------ |
| **Discover**    | understand if this is for them | unclear value prop      | {visits docs / reads positioning}    |
| **Evaluate**    | confirm it fits                | setup complexity, trust | {runs `make smoke` / demo}           |
| **First value** | experience the core benefit    | too many steps to "aha" | {completes first end-to-end journey} |
| **Habit**       | use it routinely               | doesn't fit workflow    | {N uses in first week}               |
| **Expand**      | grow usage / seats             | unclear next step       | {adds 2nd use case / team}           |

## Golden path (first hour)

1. {clone / install — link `SETUP.md`}
2. {smallest config — `.env` minimum}
3. {run — `make run` / `make smoke`}
4. {observe first value — the one screen/endpoint/metric that proves it works}

Time-to-first-value target: **{≤ 60 min}**. Measure it; treat regressions as bugs.

## Onboarding assets

- [ ] Quickstart (link `docs/quickstart/`)
- [ ] Interactive/demo mode or sample data
- [ ] Troubleshooting (link `docs/troubleshooting.md`)
- [ ] "What good looks like" reference (dashboard screenshot / expected output)

## Risks & mitigations

| Adoption risk      | Mitigation                            |
| ------------------ | ------------------------------------- |
| {e.g. heavy infra} | {minimal tier — `make setup-minimal`} |

---

## Related

- `docs/gtm/templates/gtm-brief.md`
- `SETUP.md` · `docs/quickstart/hybrid-workflow.md`
- `docs/product/templates/success-metrics.md` — activation metrics
