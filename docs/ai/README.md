# AI-Native Production Assets

> **Owner:** AI Governance Lead | **Phase:** runtime (production AI quality)
> First-class, governed assets for running agents in production: prompt versioning, model lifecycle,
> evaluation, memory governance, and observability naming. These make AI production quality
> **measurable** (improvement plan Wave 11). They consolidate truth that already lives in
> `src/agents/`, `specs/ai/`, `specs/observability/`, and the Prometheus rules — and link back to it
> rather than duplicating it.

This directory complements `docs/ai-governance/` (EU AI Act, NIST RMF, model card, autonomy
boundaries, AI-safety checklist) — it is the operational/quality layer, not the compliance layer.

## Contents

| Doc                                                        | Purpose                                                            |
| ---------------------------------------------------------- | ------------------------------------------------------------------ |
| [`prompt-registry.md`](prompt-registry.md)                 | Versioned index of every system prompt, with change protocol       |
| [`model-lifecycle.md`](model-lifecycle.md)                 | Candidate → Approved → Deprecated → Blocked + promotion checklist  |
| [`eval-scorecard.md`](eval-scorecard.md)                   | Evaluator dimensions, safety contracts, variant scorecard template |
| [`memory-governance.md`](memory-governance.md)             | Retention, deletion/DSAR, encryption, poisoning controls           |
| [`ai-observability-naming.md`](ai-observability-naming.md) | Canonical agent/LLM span & metric names                            |

## Where the truth lives (sources these docs govern)

- Prompts: `src/agents/harness/{planner,evaluator,sub_agent_registry}.py`
- Model pin: `src/shared/config.py`, `docs/dependency-manifest.yaml`; contracts: `tests/model_contract/` (ADR-0051)
- Evaluator: `src/agents/harness/evaluator.py`
- Memory: `specs/ai/agent-memory.md` (ADR-0017), migration `0003`
- Observability: `specs/observability/otel-agentic-observability.md`, `infrastructure/monitoring/prometheus/rules/agent-alerts.yaml`

## Related

- `docs/ai-governance/` — EU AI Act / NIST RMF / model card / autonomy boundaries
- `prompts/README.md` — target on-disk prompt structure
- `skills/ai/guardrails.md` · `skills/ai/harness.md`
