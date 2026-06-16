# Prompt Registry

> **Owner:** AI Governance Lead | **Status:** Living registry
> A prompt is production configuration that changes model behaviour — it deserves the same version,
> ownership, and review discipline as code. This registry is the single index of every system prompt
> the agents use, who owns it, what it is for, and how a change to it is governed.

Today the prompts live **inline in Python** (see the Location column). This registry governs them in
place; `prompts/README.md` defines the target structure for extracting them into versioned files. Do
not edit a prompt without following the change protocol below — a prompt change is a behaviour change.

---

## Registry

| Prompt ID             | Location (source of truth)                                                                                   | Purpose                                                                                                        | Model linkage        | Eval dataset                                  | Owner              | Ver |
| --------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- | -------------------- | --------------------------------------------- | ------------------ | --- |
| `harness.planner`     | `src/agents/harness/planner.py` (`_SYSTEM_PROMPT`)                                                           | TaskBrief → ProductSpec + sprint decomposition                                                                 | `settings.llm_model` | _none yet — see Gaps_                         | AI Governance Lead | 1.0 |
| `harness.evaluator`   | `prompts/evaluator/evaluate.v2.md` (loaded via `src/agents/prompts`; supersedes `evaluate.v1.md`)            | Score generator output (quality/originality/craft/functionality) + emit separate `groundedness` SLI (ADR-0080) | `settings.llm_model` | `tests/model_contract/` (indirect)            | AI Governance Lead | 2.0 |
| `subagent.<role>`     | `src/agents/harness/sub_agent_registry.py` (`system_prompt_template`)                                        | Per-role specialised sub-agent (e.g. security-reviewer)                                                        | `settings.llm_model` | _none yet_                                    | AI Governance Lead | 1.0 |
| `orchestrator.reason` | `prompts/agent-orchestrator/reason.v1.md` (static base; dynamic blocks still assembled in `orchestrator.py`) | Reason phase — static base prompt externalised; precedents + spec-contract injected at runtime                 | `settings.llm_model` | `tests/model_contract/test_spec_adherence.py` | AI Governance Lead | 1.0 |

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
- **Prompts partially externalised (ADR-0079).** Migrated: `harness.evaluator`,
  `orchestrator.reason` (static base) — loaded via `src/agents/prompts`. Still inline (phased):
  `harness.planner`, `subagent.<role>`, `harness.coordinator`, `context_manager` restore template,
  and the `spec_contract_enforcer` boundary assembly. Target structure: `prompts/README.md`.
- **`make check-inline-prompts`** (`scripts/governance/check_inline_prompts.py`, ADR-0079) blocks a
  NEW inline system prompt — or the two migrated ones reappearing — in `src/agents/**`.
- **No automated prompt-version ↔ model-version pin check.** Target: a governance gate.

---

## Related

- `prompts/README.md` — target on-disk registry structure
- `docs/ai/model-lifecycle.md` — model versions prompts are pinned to
- `docs/ai/eval-scorecard.md` — how prompt/model changes are scored
- `src/agents/harness/` — current prompt sources · `skills/ai/harness.md`
