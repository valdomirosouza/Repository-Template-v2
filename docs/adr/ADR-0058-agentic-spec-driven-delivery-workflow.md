# ADR-0058 — Agentic Spec-Driven Delivery Workflow (naming, Phase 0 Intake, AI Safety phase)

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza
**Extends:** ADR-0052 (Agentic SDLC E2E Workflow)

---

## Context

ADR-0052 established a 13-phase Agentic SDLC and the supporting artefacts (WORKFLOW.md,
machine-readable `phase-gates.yaml`, DoR/DoD/DoR-Release, RACI, HITL-GOVERNANCE). A
later documentation review (`agentic-sdlc-documentation-recommendation.md`) recommended
three improvements that ADR-0052 did not fully capture:

1. **Positioning.** The workflow was described as an "E2E workflow" without explaining
   its relationship to Gitflow and Agile. Teams need to know what it replaces (Gitflow-style
   release governance) and what it preserves (Agile principles).
2. **A missing front door.** There was no explicit **Intake & Prioritization** step where
   a problem statement, value hypothesis, **risk class**, and owner are set _before_ an Issue
   exists. The risk class is what makes the lifecycle adaptive rather than a 13-step waterfall.
3. **AI safety was implicit.** AI/LLM/agentic governance was woven across the security and
   development phases but was not a first-class, checklist-backed gate.

## Decision

Adopt **"Agentic Spec-Driven Delivery Workflow"** as the canonical name for this repository's
delivery model, documented in `docs/sdlc/agentic-spec-driven-delivery.md`, and evolve the
lifecycle from 13 to **15 phases (0–14)**:

- **New Phase 0 — Intake & Prioritization** (before Conception): problem statement, value
  hypothesis, **risk class**, owner. No Issue, no code. The risk class selects the downstream
  path (small fix / normal / high-risk / AI / security / infra).
- **New Phase 10 — AI Safety & Agent Governance** (between DevSecOps and Observability): a
  **conditional** gate, required only for AI/LLM/agentic changes (under `src/agents/` or
  `src/guardrails/`). Covers prompt-injection + data-leakage tests, tool-permission review,
  evals, auditability, and a dedicated AI Safety & Agent Governance checklist.
- The remaining phases shift accordingly (old 10–13 → 11–14).

**Positioning statement (canonical):**

> Agentic Spec-Driven Delivery is a modern SDLC operating model that replaces Gitflow-style
> release governance and reduces ceremony-heavy workflows, while preserving Agile principles
> (fast feedback, customer collaboration, iterative delivery, continuous learning).
> Agents draft, analyze, test, explain, and recommend. Humans approve, own, and operate.

**Risk-based, not waterfall.** The 15 phases are the _maximum_ path. The Risk-Based Flow table
(canonical reference) maps each change type to the gates that actually apply; low-risk work
stays lightweight.

### Artefacts updated

- `docs/sdlc/agentic-spec-driven-delivery.md` — canonical reference (Wave 1).
- `docs/process/WORKFLOW.md` — renumbered 0–14; Phase 0 + AI Safety phase added.
- `docs/process/gates/phase-gates.yaml` — `phase_gates_v1`, ids 0–14; AI Safety phase carries
  `conditional: ai_or_agent_change`.
- `docs/product/state-template.yaml` — phase range note 0–14.
- `tests/unit/process/test_governance_contracts.py` — asserts 0–14 + the two new phases.
- `CLAUDE.md`, `CLAUDE_SESSION_INIT.md`, `README.md` — naming + phase-range references.

## Consequences

### Positive

- The model's relationship to Gitflow and Agile is explicit; adoption is clearer.
- Risk class is captured at the front door, making the lifecycle genuinely adaptive.
- AI safety is a first-class, checklist-backed, CI-enforceable gate for AI/agent features.
- The machine-readable contract and its tests stay authoritative (now 0–14).

### Negative / Trade-offs

- Phase numbers shifted (old 10–13 → 11–14); references in older docs/commits point to the
  pre-evolution numbering. ADR-0052 remains valid as the origin; this ADR records the change.
- The AI Safety phase is conditional; teams must apply the risk-based flow rather than running
  it for every change.

### Neutral

- ADR-0052 is **extended, not superseded** — its decisions (two-tier HITL, budget circuit
  breaker, RACI, etc.) stand. This ADR refines naming and the phase set.

## Alternatives Considered

**Keep 13 phases and fold Intake/AI-safety into existing phases.** Rejected — Intake before
an Issue and a distinct AI-safety gate are exactly the recommendation's value; folding them in
would hide the risk-class front door and the AI governance checkpoint.

**Renumber to 1–15 (no Phase 0).** Rejected — Phase 0 communicates that Intake happens before
the tracked lifecycle (no Issue yet), matching the recommendation and common "Phase 0" usage.

---

## References

- ADR-0052 — Agentic SDLC E2E Workflow (origin)
- ADR-0054 — Machine-readable governance contracts (phase-gates.yaml)
- ADR-0053 / ADR-0055 — Runtime HITL/HOTL governance
- ADR-0015 — Autonomy levels / feature flags
- `docs/sdlc/agentic-spec-driven-delivery.md`, `docs/process/WORKFLOW.md`
- `agentic-sdlc-documentation-recommendation.md`
- Issues: #48, #49, #50
