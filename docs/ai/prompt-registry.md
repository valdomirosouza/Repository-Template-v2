# Prompt Registry

> **Owner:** AI Governance Lead | **Status:** Living registry
> A prompt is production configuration that changes model behaviour — it deserves the same version,
> ownership, and review discipline as code. This registry is the single index of every system prompt
> the agents use, who owns it, what it is for, and how a change to it is governed.

The harness and orchestrator prompts are **externalised to versioned files under `prompts/`** and
loaded byte-for-byte by `src/agents/prompt_loader.py` (ADR-0079); the remaining prompts live inline
in Python (see the Location column). This registry is the single index regardless of where a prompt
lives. `prompts/README.md` defines the on-disk layout and front-matter schema. Do not edit a prompt
without following the change protocol below — a prompt change is a behaviour change.

---

## Registry

| Prompt ID             | Location (source of truth)                                                                      | Purpose                                                                                 | Model linkage        | Eval dataset                                  | Owner              | Ver |
| --------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | -------------------- | --------------------------------------------- | ------------------ | --- |
| `harness.planner`     | `prompts/harness/planner.v1.md` (loaded by `src/agents/prompt_loader.py`)                       | TaskBrief → ProductSpec + sprint decomposition                                          | `settings.llm_model` | _none yet — see Gaps_                         | AI Governance Lead | 1.0 |
| `harness.evaluator`   | `prompts/harness/evaluator.v1.md` (loaded by `src/agents/prompt_loader.py`)                     | Score generator output (quality/originality/craft/functionality)                        | `settings.llm_model` | `tests/model_contract/` (indirect)            | AI Governance Lead | 1.0 |
| `subagent.<role>`     | `src/agents/harness/sub_agent_registry.py` (`system_prompt_template`)                           | Per-role specialised sub-agent (e.g. security-reviewer)                                 | `settings.llm_model` | _none yet_                                    | AI Governance Lead | 1.0 |
| `orchestrator.reason` | `prompts/agent-orchestrator/reason.v1.md` (static base; dynamic injection in `orchestrator.py`) | Reason phase — static base externalised; precedents + spec contract injected at runtime | `settings.llm_model` | `tests/model_contract/test_spec_adherence.py` | AI Governance Lead | 1.0 |

Model id is resolved from `src/shared/config.py` (`llm_model`, default `claude-sonnet-4-6`; backup
`claude-haiku-4-5-20251001` in `docs/dependency-manifest.yaml`). A prompt is only valid against the
model version it was evaluated on — see `docs/ai/model-lifecycle.md`.

## Required metadata per prompt

Every registered prompt must declare:

- **Owner** — accountable role (AI Governance Lead for agent prompts)
- **Purpose** — the one job this prompt does
- **Model linkage** — which model id/version it was authored and evaluated against
- **Eval dataset** — the dataset/suite that gates changes (see `docs/ai/eval-scorecard.md`)
- **Version** — bump on any semantic change; record rationale in the change log
- **Rollback** — the previous version to revert to if an eval regresses

## Change protocol (how to modify a prompt)

1. Open an Issue; treat the change as you would a code change (spec/ADR if behaviour-defining).
2. Make the edit at the source-of-truth location; **bump the version** here and note the rationale.
3. Run the relevant guardrail/eval gates: `tests/model_contract/` (if it affects safety boundaries),
   the evaluator suite, and the abuse-case suite (`uv run pytest tests/abuse_cases/ -m abuse_case`)
   if `src/agents/` or `src/guardrails/` behaviour is touched (CLAUDE.md §3.2).
4. **Never weaken a guardrail or injection-resistance instruction in a prompt** (CLAUDE.md §3.3).
5. Record the new version against the model id it was evaluated on.

## Gaps & target state (not yet implemented — do not cite as done)

- **No per-prompt eval dataset** for planner/sub-agents yet. Target: a small golden dataset per
  prompt with pass thresholds, wired like `tests/model_contract/`.
- **Sub-agent prompts not yet externalised.** The harness planner/evaluator and orchestrator Reason
  base are externalised (ADR-0079); `subagent.<role>` templates remain inline. Layout: `prompts/README.md`.
- **No automated prompt-version ↔ model-version pin check.** Target: a governance gate.

---

## Related

- `prompts/README.md` — target on-disk registry structure
- `docs/ai/model-lifecycle.md` — model versions prompts are pinned to
- `docs/ai/eval-scorecard.md` — how prompt/model changes are scored
- `src/agents/harness/` — current prompt sources · `skills/ai/harness.md`
