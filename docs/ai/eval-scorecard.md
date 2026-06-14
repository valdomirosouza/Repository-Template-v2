# AI Evaluation Scorecard

> **Owner:** AI Governance Lead | **Status:** Living standard
> Defines how agent output quality and safety are measured, and provides a comparable scorecard for
> model/prompt variants. It formalises the scoring the Evaluator already performs and the safety the
> model-contract suite already checks — into one reviewable artefact per change.

---

## What is scored today

### 1. Evaluator quality dimensions (`src/agents/harness/evaluator.py`)

The harness Evaluator scores generator output on four dimensions, each `0.0–1.0`:

| Dimension       | Meaning                                |
| --------------- | -------------------------------------- |
| `quality`       | functional coherence vs the spec       |
| `originality`   | deliberate design vs template defaults |
| `craft`         | error handling, edge cases, structure  |
| `functionality` | all success criteria met               |

**Pass rule:** every dimension must meet `settings.harness_evaluator_pass_threshold` (default
`0.75`); any dimension below threshold = FAIL. Each evaluation is audit-logged before returning.

### 2. Safety contract (`tests/model_contract/`)

Gating safety suites (ADR-0051), run by `ci-model-contract.yml`:

| Suite                      | Asserts                                                        |
| -------------------------- | -------------------------------------------------------------- |
| `test_refusal_behavior.py` | refuses jailbreaks, authority overrides, credential extraction |
| `test_spec_adherence.py`   | respects `[SPEC_CONTRACT]` boundaries                          |
| `test_pii_non_leakage.py`  | does not echo/infer PII from masked context                    |

### 3. Risk routing (`src/shared/config.py`)

`hitl_risk_threshold` (default `0.4`) routes higher-risk actions to HITL; the human-review risk
threshold is `≥ 0.7` (CLAUDE.md §3.2 LLM09). These are governance gates, not quality scores, but
belong on the scorecard because they bound autonomous action.

## Scorecard template (per model/prompt variant)

Fill one per candidate change (new model version, new prompt version) and attach to the PR.

```text
Scorecard — {model_id @ contract vX} / {prompt_id vY}
Date: YYYY-MM-DD   Evaluated by: {name}   Baseline: {prior model/prompt}

Quality (threshold 0.75, all must pass)
  quality:        0.__   originality:   0.__
  craft:          0.__   functionality: 0.__   → PASS / FAIL

Safety (tests/model_contract/ — must be green)
  refusal:        pass/fail
  spec_adherence: pass/fail
  pii_non_leakage:pass/fail

Abuse cases (must not regress, ADR-0050): {count} pass / {baseline}
Cost & latency:  token_cost_p95 {n}   llm_call p99 {n}s   Δ vs baseline {±}
Decision: APPROVE / REJECT   Rationale: ...
```

## Regression thresholds & sampling

- **Quality:** no dimension may drop below `0.75`; flag any ≥ 0.05 regression vs baseline.
- **Safety:** zero tolerance — any contract-suite failure blocks promotion.
- **Abuse cases:** count must never decrease (ADR-0050).
- **Human review sample rate:** sample autonomous resolutions for human spot-check; route anything at
  risk ≥ 0.7 to HITL.

## Gaps & target state (not yet implemented)

- **No standing eval dataset / leaderboard** for prompt/model variants yet. Target: a golden eval set
  with the scorecard above auto-generated in CI, and a variant leaderboard.
- **Hallucination/factuality metric** is not yet computed; tracked under `docs/ai/ai-observability-naming.md`.

---

## Related

- `src/agents/harness/evaluator.py` · `skills/ai/harness.md`
- `docs/ai/model-lifecycle.md` · `tests/model_contract/` (ADR-0051)
- `specs/observability/agent-performance.md` · `docs/ai/ai-observability-naming.md`
