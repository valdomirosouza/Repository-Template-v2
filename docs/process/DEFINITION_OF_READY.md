# Definition of Ready (DoR)

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Tech Lead | **Approver:** Governance Council
> **ADR:** ADR-0052 | **Workflow phase:** Phase 3 — Grooming

A GitHub Issue may **not** enter a sprint until **ALL** of the following criteria are met. An Issue that fails DoR stays in the backlog for further refinement.

---

## DoR Checklist

- [ ] **Problem statement written** — Issue body explains what user/business problem this solves (not just what to build). For product-facing features, a `docs/product/FEAT-{id}/problem-framing-canvas.md` is recommended (template: `docs/product/templates/problem-framing-canvas.md`)
- [ ] **Personas & value hypothesis identified** _(product-facing features)_ — user vs buyer persona and a falsifiable value hypothesis captured (templates: `docs/product/templates/personas.md`, `value-hypothesis.md`), OR "N/A: internal-only" stated
- [ ] **Success metrics defined** _(product-facing features)_ — north-star + guardrail metrics with named instruments (template: `docs/product/templates/success-metrics.md`), OR "N/A: no measurable user-facing outcome"
- [ ] **GTM brief drafted** _(features intended as reusable products)_ — ICP, positioning, and adoption path captured (templates under `docs/gtm/templates/`), OR "N/A: internal-only"
- [ ] **Discovery doc linked** — `docs/product/FEAT-{id}/discovery.md` exists and is linked in the Issue body, OR an explicit "N/A: no discovery phase needed" note is present (spike and chore Issues are exempt)
- [ ] **NFR doc approved** — `docs/product/FEAT-{id}/nfr.md` exists and has been approved by the Security Lead, OR "N/A: no new PII surface or security threat" is explicitly stated and confirmed by Tech Lead
- [ ] **Acceptance criteria written** — Gherkin-format `Given / When / Then` scenarios in the Issue body, reviewed by Product Owner
- [ ] **Feature spec template created** — `specs/features/FEAT-{id}/feature-spec.md` exists with sections 1–5 complete (Goal, User Stories, API Delta, Event Delta, Data Model)
- [ ] **Size label applied** — one of `size: S`, `size: M`, `size: L`, `size: XL`
- [ ] **Component labels applied** — one or more of `component: api`, `component: frontend`, `component: infra`, `component: agent`
- [ ] **Risk class assigned** (ADR-0058 Phase 0) — one of: small fix · normal feature · high-risk feature · AI/LLM/agentic feature · security-sensitive · infrastructure/platform. Determines which downstream gates apply (risk-based flow).
- [ ] **ADR need identified** — an ADR is linked/planned for the architectural decision, OR "N/A: no architectural decision" is explicitly stated.
- [ ] **Threat model need identified** — a threat model is required (security/privacy/AI risk) and planned, OR "N/A: no new threat surface" is explicitly stated.
- [ ] **Observability expectations defined** — the critical user journey, golden signals, and required logs/metrics/traces/alerts are noted (or "N/A: no runtime surface").
- [ ] **Test strategy outlined** — the test types in scope (unit / integration / contract / abuse-case / performance) and the coverage threshold aligned to the risk class are stated.
- [ ] **Tech Lead has commented** — at least one comment from a Tech Lead confirming the Issue is technically sound and unblocked

---

## Exemptions

| Issue type       | Exempt from                                                  |
| ---------------- | ------------------------------------------------------------ |
| `type: bug`      | Discovery doc, NFR doc, Feature spec template                |
| `type: spike`    | NFR doc, Feature spec template, AC in Gherkin                |
| `type: chore`    | Discovery doc, NFR doc, Feature spec template, AC in Gherkin |
| `type: security` | Discovery doc; NFR doc required                              |

Even exempt Issues must have a clear Problem Statement, size label, and Tech Lead comment before entering a sprint.

---

## Who Checks DoR?

DoR is checked by the **Tech Lead** during the Grooming Ceremony (Phase 3, Step 4). The CI `harness/governance.yml` enforces a subset mechanically (spec file existence, ADR references). The remaining criteria are human-verified.

---

## Related

- `docs/process/DEFINITION_OF_DONE.md` — criteria for completing a story
- `docs/process/DEFINITION_OF_RELEASE.md` — criteria for promoting to production
- `docs/process/RACI.md` — who owns each gate
- `docs/process/WORKFLOW.md` — full 15-phase (0–14) lifecycle
