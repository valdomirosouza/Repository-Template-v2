# ADR-0054 — Machine-Readable Governance Contracts (Structured Output, Phase Gates, Feature State, Risk Calibration)

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

> **Phase-model note ([ADR-0058](ADR-0058-agentic-spec-driven-delivery-workflow.md)):**
> the Context below references the **13-phase** lifecycle that was current when this ADR
> was written. The lifecycle has since evolved to **15 phases (0–14)** and the
> `phase-gates.yaml` machinery defined here was updated accordingly (ids 0–14, with a
> conditional Phase 10 AI Safety gate). The decisions in this ADR remain in force.

---

## Context

After Wave A (ADR-0053) made the runtime _enforcement_ path correct, an audit
against the _Agentic SDLC Repository Improvement Directive_ (§8–§9) surfaced four
governance gaps where the contract existed only as prose or convention — readable
by humans, but not enforceable by agents or CI:

- **P1-10 — Weak agent output contract.** The orchestrator asked the LLM for
  `{action, parameters, risk_score}`. There was no schema validation, and the
  LLM's self-reported `risk_score` could be mistaken for authoritative. Malformed
  or partial output could slip through.

- **P1-9 — Phase gates were Markdown-only.** `docs/process/WORKFLOW.md` documents
  13 phases and their gates, but an agent could not _query_ "is `deploy` allowed in
  the current phase?" — it would have to parse prose.

- **P1-7 — No compact per-feature state.** Determining a feature's current phase
  meant reading discovery.md, nfr.md, the spec, and the Issue. There was no
  machine-readable state record.

- **P1-4 — Risk scoring had no golden dataset.** The 5-factor weights existed, but
  nothing pinned expected score → routing behaviour, so a weight or keyword change
  could silently shift oversight.

## Decision

Introduce four machine-readable governance contracts.

### 1. `agent_action_v1` structured output schema (P1-10)

New module `src/agents/schemas/agent_action_v1.py` defines the strict envelope the
Reason stage requires and `parse_agent_action()` validates it **fail-closed**:

- Unparseable JSON, non-object payloads, or a missing `action_type` →
  `is_valid=False`, `action_type="unknown"`.
- Out-of-set enum values (`target_environment`, `operation`, `data_classification`),
  wrong primitive types, or an unsupported `schema_version` → `is_valid=False` with
  recorded `validation_errors`.
- Missing _optional_ fields are filled with safe defaults.

The orchestrator routes `is_valid=False` to HITL (`oversight_mode="HITL_SCHEMA_INVALID"`)
— invalid output never proceeds silently. The LLM's `agent_confidence` is advisory
only; the system risk scorer owns the final score (ADR-0011/0053).

**Backward compatibility:** a legacy `{"action": ..., "parameters": ...}` payload
(no `schema_version`) is accepted and reported valid, provided an action name is
present and any declared fields are well-formed. Only explicitly declared governance
fields are merged into `parameters`, so the proposed parameters reflect what the
agent actually sent.

### 2. Machine-readable phase gates (P1-9)

New `docs/process/gates/phase-gates.yaml` (schema `phase_gates_v1`) projects all 13
phases into structured records: `required_artifacts`, `required_approvals`,
`ci_checks`, `blocking`, `allowed_agent_actions`, `prohibited_agent_actions`, and
`exit_criteria`. `docs/process/WORKFLOW.md` remains the source of truth; the YAML is
its projection and must be kept in sync. Default-deny: an action not listed in
`allowed_agent_actions` is treated as prohibited.

### 3. Feature-level state manifests (P1-7)

New `docs/product/state-template.yaml` (schema `feature_state_v1`) is copied to
`docs/product/FEAT-{id}/state.yaml` per feature. It records `current_phase`,
`approvals`, `gates_passed`, `artifacts`, and a convenience projection of the
current phase's allowed/prohibited actions. An agent resolves phase from
`state.yaml`, then consults `phase-gates.yaml` — no Markdown parsing.

### 4. Risk calibration golden dataset (P1-4)

New `tests/unit/agents/test_risk_calibration.py` pins ≥ 12 scenarios
(scenario → expected score ±0.005 → tier → route) spanning LOW/MEDIUM/HIGH and
HOTL/HITL. If a change to `risk_scorer.py` moves any scenario across a routing
boundary, CI fails — forcing an explicit, reviewed recalibration.

`tests/unit/process/test_governance_contracts.py` validates the two YAML contracts
(structure, vocabulary, role declarations, allowed/prohibited disjointness, and
template ↔ gate consistency).

## Consequences

### Positive

- Agent output is schema-validated; malformed output is routed to HITL, never executed silently.
- Phase gates and feature state are queryable by agents and CI — process governance becomes programmatic.
- Routing behaviour is locked by a golden dataset; silent risk drift is caught in CI.
- The LLM's self-reported confidence is explicitly advisory; the system scorer is authoritative.

### Negative / Trade-offs

- `phase-gates.yaml` and `state.yaml` must be kept in sync with `WORKFLOW.md` and the live feature state — drift is possible if updated carelessly (mitigated: the contract test enforces template ↔ gate consistency).
- Recalibrating risk weights now requires updating the golden dataset in the same PR (intentional friction).

### Neutral

- The schema is additive: legacy short-form payloads still validate, so existing call sites and fixtures keep working.
- `phase-gates.yaml` governs _process_; ADR-0053 runtime enforcement governs _execution_. Both apply independently.

## Alternatives Considered

**Use `jsonschema` for envelope validation:** Rejected for now — adds a dependency
for a small, fixed schema. The hand-rolled validator is dependency-free and returns
structured errors. Can be revisited if the schema grows.

**Generate `phase-gates.yaml` from `WORKFLOW.md` automatically:** Rejected for this
wave — a parser over hand-written Markdown tables is brittle. Manual sync with a
consistency test is simpler and reliable; automation can come later.

**Strict (non-backward-compatible) schema:** Rejected — would break existing
fixtures and call sites with no governance benefit. Legacy payloads are validated
leniently but still fail-closed on bad enums/types.

---

## References

- ADR-0052 — Agentic SDLC E2E Workflow (13 phases)
- ADR-0053 — Runtime correctness (HITL/autonomy/tool enforcement)
- ADR-0011 — HITL/HOTL Model
- ADR-0048 — Zero-trust tool registry
- Spec: `specs/ai/hitl-hotl.md`, `specs/ai/agent-design.md`
- Directive: `Agentic-SDLC-Repository-Improvement-Directive.md` §8–§9 (P1-4, P1-7, P1-9, P1-10)
- Issue: #44
