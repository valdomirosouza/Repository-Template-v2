# ADR-0079 — Prompt Externalisation and a No-Inline-Prompt CI Gate

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** Valdomiro Souza
**Spec:** N/A — governed by `prompts/README.md` + `docs/ai/prompt-registry.md` (Issue #269)
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0014](ADR-0014-multi-agent-harness-strategy.md) (harness), [ADR-0072](ADR-0072-versioned-control-matrices.md) (machine-verified governance), [ADR-0051](ADR-0051-model-contract-testing.md) (model-contract gate)

## Context

An LLM system prompt is production configuration: editing one word changes model behaviour,
yet inline prompt string literals are invisible to review, impossible to diff or roll back
independently of code, carry no owner, no version, and no model pin. `prompts/README.md` and
`docs/ai/prompt-registry.md` already defined the _target_ — versioned files under
`prompts/<area>/<name>.vN.md` with YAML front-matter (id, version, owner, model, eval_dataset,
supersedes) — but no prompt had been extracted and nothing stopped new inline prompts being added.

Issue #269 scopes the first, lowest-risk slice: externalise the **two named static prompts**
(`harness.evaluator` and the orchestrator Reason-phase **static base**), and add a CI gate that
prevents regression. The remaining inline prompts are dynamic or role-parameterised and are left
for later phases — externalising them all at once would be a large, behaviour-sensitive change.

## Decision

We will externalise the two prompts and guard the boundary with a deterministic CI gate.

1. **Two prompts move to versioned files.** `prompts/evaluator/evaluate.v1.md` and
   `prompts/agent-orchestrator/reason.v1.md`, each with the front-matter schema and the prompt
   **body byte-identical** to the former inline constant. For the orchestrator, **only the static
   base** moves; the dynamic precedents block and spec-contract boundary are still assembled in
   `orchestrator.py` at runtime.
2. **A small synchronous loader** (`src/agents/prompts/loader.py`) maps prompt id → path, parses and
   validates the front-matter, and returns the verbatim body. It uses the **standard library only**
   (no new dependency): front-matter is flat `key: value` and is parsed directly; the body lives in
   a fenced `text` block so the body returned is exactly the former string. `evaluator.py` and
   `orchestrator.py` load via this loader instead of an inline constant — `.format(threshold=...)`
   and the dynamic assembly are unchanged.
3. **A no-inline-prompt gate** (`scripts/governance/check_inline_prompts.py`, `make
check-inline-prompts`, wired into `.github/workflows/ci-ai-safety.yml`) fails (exit 1,
   `::error::`) when a system-prompt-shaped literal appears in `src/agents/**/*.py` outside an
   allow-list. The allow-list pins the not-yet-migrated prompts; it deliberately **excludes** the
   two now-externalised prompts, so either reappearing inline fails the build.
4. **Phased migration of the remaining inline prompts.** The allow-list is the backlog. Future
   phases externalise, in order of risk: `harness.planner` → `subagent.<role>`
   (`sub_agent_registry`) → `harness.coordinator` self-reflection prompts → the `context_manager`
   restore template. The `spec_contract_enforcer` permission-boundary assembly stays in code (it is
   computed, not a static prompt). Each migration removes its allow-list entry, keeping the gate
   monotonically stricter.

### Fenced-body note

The repository environment runs a Markdown formatter on write that reflows prose (alignment,
indentation, list spacing). To keep the body byte-identical we store it inside a ` ```text ` fenced
block, which formatters preserve verbatim; the loader extracts the fence content. This is a small,
deliberate deviation from the raw-body layout sketched in `prompts/README.md`, motivated solely by
the byte-identity requirement; the front-matter schema is unchanged.

## Consequences

### Positive

- Each migrated prompt now has an owner, a version, a pinned model, and a diffable change history —
  the same controls as code/config — and can be reviewed and rolled back independently of code.
- The CI gate makes "no new inline prompts" a machine-verified invariant, not a convention.
- Behaviour is provably unchanged: unit tests assert the loaded body is byte-identical to frozen
  copies of the former inline constants.

### Negative / Trade-offs

- A prompt is now loaded from disk at import; a missing/corrupt file raises `PromptError` at import
  rather than failing silently. This is the intended fail-closed behaviour but is a new failure mode.
- The fenced-body indirection is slightly less obvious than a raw body; documented above and in the
  loader docstring.
- The allow-list must be tended as phases land (stale entries weaken the gate) — called out in the
  registry's Gaps section.

### Neutral

- Five prompts remain inline by design (phased); the registry and allow-list are the single source
  of truth for which.

## Compliance & Risk

- **Controls affected:** OWASP LLM (governance of prompt changes); CLAUDE.md §3.3 (guardrail
  prompts must never be weakened — the gate plus byte-identity tests enforce no silent drift).
- **Data classification impact:** none — prompts contain no PII (L4).
- **Autonomy impact:** none — no change to HITL/HOTL routing, feature flags, or risk scoring; the
  evaluator/orchestrator load the same prompt text they used before.
- **Review/expiry:** permanent; revisit as each remaining inline prompt is externalised.

## Related

- `prompts/README.md` · `docs/ai/prompt-registry.md` (registry + change protocol)
- `src/agents/prompts/loader.py` · `scripts/governance/check_inline_prompts.py`
- `tests/unit/agents/test_prompt_loader.py` · `docs/adr/adr-review-checklist.md`
