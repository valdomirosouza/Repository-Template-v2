# Go-to-Market (GTM) Layer

> **Owner:** Product Owner (with Founder/Marketing) | **Phase:** 1–2 (Conception & Discovery)
> **Status:** Living directory
>
> This directory holds GTM artefacts for features and capabilities that are meant to become
> **reusable products** — not just internal increments. It complements the engineering discovery
> artefacts in `docs/product/` by answering the market-facing questions: who buys, why us, how they
> adopt, and how we talk about it.

---

## When to use this layer

Use GTM artefacts when a feature is intended to be **packaged, positioned, sold, or adopted by
parties outside the building team** (other teams, customers, or the open-source community). Purely
internal plumbing does not need a GTM brief — note "N/A: internal-only" in the discovery doc.

| Question                           | Artefact                        |
| ---------------------------------- | ------------------------------- |
| Who is the ideal customer & buyer? | `templates/gtm-brief.md`        |
| Why us, vs the alternatives?       | `templates/positioning.md`      |
| How do users get to first value?   | `templates/adoption-plan.md`    |
| How does the team sell/explain it? | `templates/sales-enablement.md` |

## How GTM connects to discovery

```
problem-framing-canvas.md ─┐
personas.md ───────────────┼─→ gtm-brief.md ─→ positioning.md ─→ adoption-plan.md
value-hypothesis.md ───────┘                                  └─→ sales-enablement.md
```

The user/buyer personas and the value hypothesis from `docs/product/` are **inputs** to the GTM
brief — do not duplicate them, link them.

## Workflow

1. Copy the relevant template into `docs/gtm/FEAT-{id}/` (or a product-level folder for cross-cutting GTM).
2. If agent-generated, prepend the Agent-Disclosure Header (see `docs/product/README.md`).
3. Review with Product Owner; positioning/pricing assumptions are **hypotheses** until validated.

---

## Related

- `docs/product/README.md` — engineering discovery artefacts
- `docs/product/templates/personas.md` — user vs buyer persona
- `docs/governance/traceability-matrix.md`
