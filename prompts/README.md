# Prompts

> **Owner:** AI Governance Lead | **Status:** Target structure (scaffold)
> This directory defines the **target** on-disk home for versioned LLM prompts. Today the prompts
> are still inline in Python (see `docs/ai/prompt-registry.md` for the authoritative registry and
> the source-of-truth locations). This README establishes the convention and the migration path; it
> does not change runtime behaviour.

## Why externalise prompts

Inline prompt strings are invisible to review and impossible to diff or roll back independently of
code. Externalised, versioned prompts give each one an owner, a change history, a pinned model
version, and an evaluation gate — the same controls we already apply to code and config.

## Target layout

```
prompts/
├── README.md                 ← this file
├── agent-orchestrator/
│   └── reason.vN.md          ← orchestrator Reason-phase prompt (currently dynamic, in code)
└── evaluator/
    └── evaluate.vN.md        ← evaluator scoring prompt (currently evaluator.py:_SYSTEM_PROMPT)
```

Each prompt file carries front-matter:

```yaml
---
id: harness.evaluator
version: 1.0
owner: AI Governance Lead
model: claude-sonnet-4-6 # the model id this prompt was evaluated against
eval_dataset: tests/model_contract/ # gate that must pass before promotion
supersedes: null
---
```

## Migration path (inline → versioned files)

1. Copy the inline prompt verbatim into `prompts/<area>/<name>.v1.md` with front-matter.
2. Load it from the file at startup (no behaviour change vs the inline string).
3. Add a test asserting the loaded prompt equals the registered version + model pin.
4. Update `docs/ai/prompt-registry.md` Location column to the file path.

Until step 2 ships, **the Python source remains the source of truth** — see the registry.

## Rules

- A prompt change is a **behaviour change**: follow the change protocol in `docs/ai/prompt-registry.md`.
- Never weaken guardrail/injection-resistance instructions in a prompt (CLAUDE.md §3.3).
- Pin every prompt to the model version it was evaluated on (`docs/ai/model-lifecycle.md`).

---

## Related

- `docs/ai/prompt-registry.md` — authoritative registry & change protocol
- `docs/ai/eval-scorecard.md` · `docs/ai/model-lifecycle.md`
- `src/agents/harness/` — current prompt sources
