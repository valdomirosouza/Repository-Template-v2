# ADR-0080 — Groundedness Scoring as an SLI

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** AI Governance Lead
**Spec:** N/A — operational policy (see `docs/ai/eval-scorecard.md`, `docs/ai/ai-observability-naming.md`)
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0051](ADR-0051-model-contract-testing.md), [ADR-0079](ADR-0079-prompt-externalization-and-no-inline-prompt-gate.md)

---

## Context

CLAUDE.md §3.6 (Grounding & Non-Fabrication) makes a hallucinated API, path, or fact the
highest-severity failure mode for an agentic system, because it propagates cleanly through
spec → design → code. Today that rule is enforced only by prose and human review: there is no
machine-checked signal that an agent answer is actually supported by the context it was given.

The harness Evaluator already scores generator output on four dimensions
(`quality`/`originality`/`craft`/`functionality`) in `src/agents/harness/evaluator.py`, and the
model-contract suite (`tests/model_contract/`, ADR-0051) already gates safety behaviours
(refusal, PII non-leakage, spec adherence). The observability naming standard
(`docs/ai/ai-observability-naming.md` §Gaps) reserves — but does not yet emit —
`agent_hallucination_flagged_total` and a grounding ratio. We need to close that gap with a
measurable, error-budget-carrying signal without destabilising the just-touched Evaluator model
(ADR-0079).

## Decision

We will treat **groundedness** — the share of an answer's claims that are supported by the
provided context — as a first-class **Service Level Indicator (SLI)**, defined and enforced two
ways:

1. **Scored by a model-contract test** (`tests/model_contract/test_groundedness.py`): real-model
   cases assert grounded answers are supported by a known context, and that trap cases (context
   lacks the answer) yield an "I don't know" refusal rather than a fabrication. It runs under the
   existing `@pytest.mark.model_contract` marker and `ci-model-contract.yml` budget — no new
   workflow.
2. **Emitted as OTel/Prometheus metrics**: `agent_groundedness_score` (Gauge, 0.0–1.0) carrying
   the error budget, and `agent_hallucination_flagged_total` (Counter) for unsupported-claim
   events, recorded via `record_groundedness(...)` in `src/observability/metrics.py`, using the
   names reserved in `docs/ai/ai-observability-naming.md`.

We will record groundedness as a **separate safety SLI, NOT a fifth `EvaluatorScore` dimension.**
We deliberately do **not** add a field to `EvaluatorScore`, change its pass rule, or alter its
system prompt. That keeps this change atomic and non-breaking, isolates it from the Evaluator
model that ADR-0079 just modified, and lets groundedness carry its own error budget and gate
independently of generator-quality scoring.

## Consequences

### Positive

- CLAUDE.md §3.6 becomes **measurable and gated** rather than advisory.
- Reuses existing infrastructure: the model-contract marker/CI budget and the reserved metric
  names — no new workflow, no new naming.
- Independent error budget: a groundedness regression is visible and alertable on its own,
  without entangling generator-quality scoring.

### Negative / Trade-offs

- Groundedness lives in two places (a contract test and a metric) instead of one Evaluator field;
  contributors must know it is a separate signal.
- Heuristic/keyword assertions in the contract test are coarser than a dedicated grounding model;
  they catch blatant fabrication, not subtle unsupported nuance.
- The metric is only as good as its callers — wiring `record_groundedness` into runtime grounding
  checks is follow-up work, not part of this ADR.

### Neutral

- The `agent_id` / `sprint_id` labels are kept minimal per the naming standard to avoid
  unbounded cardinality.

## Alternatives Considered

- **Add a 5th `EvaluatorScore` dimension (`groundedness`).** Rejected: it would change the
  Evaluator pass rule and system prompt immediately after ADR-0079 touched that model, coupling an
  orthogonal safety signal to generator-quality scoring and removing its independent error budget.
- **Do nothing (keep §3.6 as prose).** Rejected: leaves the highest-severity failure mode with no
  machine-checked signal.
- **A standalone grounding-judge service.** Rejected as premature: heavier than needed for the
  current atomic step; the contract test + metric establish the SLI and can be upgraded later.

## Compliance & Risk

- **Controls affected:** OWASP LLM09 (overreliance / hallucination) — see
  `specs/security/owasp-genai-control-matrix.yaml`. Reinforces CLAUDE.md §3.6.
- **Data classification impact:** none — test context is synthetic (fictional entities, no PII).
- **Autonomy impact:** none — does not change HITL/HOTL behaviour or any feature flag; the
  Evaluator pass rule is unchanged.
- **Review/expiry:** permanent (revisit if a dedicated grounding-judge replaces the heuristic test).

---

## Update — 2026-06-16 (runtime wiring)

The follow-up flagged under _Consequences → Negative_ ("wiring `record_groundedness` into runtime
grounding checks is follow-up work") is now done. The harness Evaluator
(`src/agents/harness/evaluator.py`, prompt `prompts/evaluator/evaluate.v2.md`) reuses its **existing
single LLM call** to also return an LLM-judged `groundedness` (0.0–1.0) and emits it via
`record_groundedness(score=..., flagged=(score < threshold), agent_id="evaluator", sprint_id=...)`.

The decision is **unchanged**: groundedness stays a **separate metric, not a 5th `EvaluatorScore`
dimension**, and the Evaluator `passed` rule (all four quality dimensions ≥ threshold) is untouched.
The field is optional and backward-compatible — a missing or non-numeric value is skipped, never
fabricated. Scope: the metric is populated when the Evaluator runs (harness-mode evaluation cycles).
No new LLM call is added.

---

## Related

- `docs/adr/README.md` — master index & lifecycle definition
- `docs/adr/adr-review-checklist.md` — checklist to apply before marking this ADR `Accepted`
- `docs/ai/eval-scorecard.md` · `docs/ai/ai-observability-naming.md`
- `tests/model_contract/test_groundedness.py` · `src/observability/metrics.py`
