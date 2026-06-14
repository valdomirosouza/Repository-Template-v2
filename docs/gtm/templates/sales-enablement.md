# Sales Enablement — {product / FEAT-id}

> **Owner:** Product Owner (with Sales/DevRel) | **Status:** Draft | Under Review | Approved
> Copy to `docs/gtm/FEAT-{id}/sales-enablement.md`. When agent-generated, prepend the
> Agent-Disclosure Header (see `docs/product/README.md`).
>
> Equips anyone (sales, DevRel, a founder, or an internal champion) to explain the product and
> handle the predictable objections. Keep answers honest — "uncertain — verify" beats a fabricated
> claim (CLAUDE.md §3.6).

---

## Elevator pitch

> {2–3 sentences — pull from `positioning.md` so they stay consistent}

## Value summary by persona

| Persona          | Their problem | What we do | Proof                 |
| ---------------- | ------------- | ---------- | --------------------- |
| {economic buyer} | {…}           | {…}        | {metric / case study} |
| {end user}       | {…}           | {…}        | {demo / quote}        |

## Discovery questions to ask

- {question that surfaces the trigger event}
- {question that quantifies the pain}

## Objection handling

| Objection                            | Honest response                                           |
| ------------------------------------ | --------------------------------------------------------- |
| "We can build this ourselves."       | {what we've already solved — governance, guardrails, SRE} |
| "Is it safe to let agents act?"      | {HITL/HOTL + guardrails — link `docs/ai-governance/`}     |
| "How does it handle our compliance?" | {LGPD/GDPR/SOX/ISO posture — link `docs/governance/`}     |
| "What's the lock-in?"                | {open formats, exportable artefacts, OSS core}            |

## FAQ

- **Q:** {common question} — **A:** {answer}
- **Q:** {pricing/packaging} — **A:** {link `gtm-brief.md` — mark hypotheses as such}

## Competitive one-liners

| Vs {alternative} | "{one honest sentence on the trade-off}" |
| ---------------- | ---------------------------------------- |

## Trust & security talking points

- {data handling, encryption at rest, audit trail, autonomy controls}
- Link the Trust Center / security posture (`SECURITY.md`, `docs/governance/`).

---

## Related

- `docs/gtm/templates/positioning.md`
- `docs/gtm/templates/gtm-brief.md`
- `SECURITY.md` · `docs/ai-governance/`
