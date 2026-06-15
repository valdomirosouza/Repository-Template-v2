# ADR-0079 — Prompt Externalization & No-Inline-Prompt CI Gate

**Status:** Proposed
**Date:** 2026-06-15
**Authors:** Valdomiro Souza
**Spec:** N/A — operational policy (registry: `docs/ai/prompt-registry.md`)
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0015](ADR-0015-feature-flag-strategy.md) (feature-flag / autonomy governance), [ADR-0051](ADR-0051-model-behavioral-contracts.md) (model behavioural contracts), [ADR-0060](ADR-0060-task-atomicity-skill-budget.md) (task atomicity / one reviewable artifact)

---

## Context

Every system prompt the agents use is currently an **inline Python string**, despite
`prompts/README.md` and `docs/ai/prompt-registry.md` already defining a target on-disk home and an
authoritative registry. The source-of-truth locations are:

- `src/agents/harness/planner.py:33` (`_SYSTEM_PROMPT`) — TaskBrief → ProductSpec + sprint decomposition.
- `src/agents/harness/evaluator.py:35` (`_SYSTEM_PROMPT`) — scores generator output; format-injected with `threshold`.
- `src/agents/orchestrator/orchestrator.py:207-221` — the Reason-phase prompt, assembled dynamically at runtime.

A prompt in production configuration changes model behaviour as much as code does, yet inline
strings are invisible to focused review, cannot be diffed or rolled back independently of code,
carry no owner, and pin to no evaluated model version. The registry governs them _in place_ today
but explicitly lists "Prompts not yet externalised" and "No automated prompt-version ↔
model-version pin check" as open gaps. Nothing prevents a new inline prompt being added to
`src/agents/`, so the gap silently widens with every agent feature (CLAUDE.md §3.6 — a control we
assert but do not enforce is a false assurance).

## Decision

We will externalise agent prompts to versioned files under `prompts/`, load them through a single
deterministic loader, and enforce a no-new-inline-prompt CI gate so the externalised state cannot
regress.

1. **On-disk format.** Each prompt lives at `prompts/<area>/<name>.vN.md` with the front-matter
   schema already defined in `prompts/README.md`:

   ```yaml
   ---
   id: harness.evaluator # stable registry id (matches docs/ai/prompt-registry.md)
   version: 1.0 # semantic; bump on any behaviour-defining change
   owner: AI Governance Lead
   model: claude-sonnet-4-6 # the model id this prompt was evaluated against
   eval_dataset: tests/model_contract/ # gate that must pass before promotion
   supersedes: null # prior prompt id@version, or null
   ---
   ```

   The Markdown body below the front-matter is the prompt text, copied **verbatim** from the inline
   string so step-1 migration is behaviour-preserving.

2. **Loader.** A single module `src/agents/prompt_loader.py` exposes `load_prompt(id: str) -> str`:
   a deterministic, total `id → path` mapping (`harness.evaluator` → `prompts/evaluator/evaluate.v1.md`),
   parsing of the front-matter, return of the body only, and an in-process cache (load once at
   startup). Unknown id or missing file raises — there is no silent fallback to an inline default.
   The loader validates that the `model` front-matter is consistent with the active model per
   `docs/ai/model-lifecycle.md`; a prompt pinned to a retired model fails loudly (closes the
   "no automated prompt-version ↔ model-version pin check" gap, ADR-0051).

3. **CI gate.** A governance check (`scripts/governance/check_inline_prompts.py`, wired into
   `harness/code-check.yml` alongside the existing matrix/binding/test-integrity gates) **fails the
   build on any NEW inline system-prompt string in `src/agents/`**, with `src/agents/prompt_loader.py`
   as the sole allowed exception. The gate is baseline-driven (like `check_test_integrity.py`): the
   three known inline prompts above are recorded in a baseline so the gate blocks _additions_ and
   _regressions_ without forcing a big-bang migration. Each baseline entry must reference a
   migration tracking issue; removing an entry (i.e. completing a migration) is always allowed.

4. **Registry stays authoritative.** `docs/ai/prompt-registry.md` remains the human index; on each
   migration its Location column moves from the Python path to the `prompts/...` file path, per the
   migration path already documented there and in `prompts/README.md`.

### Migration path (which prompts move first)

Externalise the three currently-inline prompts in registry order, one PR (one reviewable artifact,
ADR-0060) per prompt:

1. `harness.evaluator` → `prompts/evaluator/evaluate.v1.md` — simplest (single static string with a
   `{threshold}` placeholder; already has an indirect eval dataset in `tests/model_contract/`).
2. `harness.planner` → `prompts/agent-orchestrator/planner.v1.md` — static string, no per-prompt
   eval dataset yet (tracked as a registry gap; not blocking externalisation).
3. `orchestrator.reason` → `prompts/agent-orchestrator/reason.v1.md` — last, because it is assembled
   dynamically (precedent injection, schema block); externalise the **static template** and keep the
   runtime interpolation in code.

For each: copy verbatim → load via `prompt_loader` → add a test asserting the loaded prompt equals
the registered version + model pin → update the registry Location column → drop the baseline entry.

## Consequences

### Positive

- Each prompt gains an owner, a diffable change history, a pinned evaluated model, and an eval gate —
  the same controls already applied to code and config, closing two named registry gaps.
- The CI gate makes "prompts are externalised" an enforced invariant, not aspirational prose; the
  inline-prompt count can only go down (CLAUDE.md §3.6).
- Prompt rollback becomes independent of code rollback (revert one Markdown file).

### Negative / Trade-offs

- Adds an indirection (file load + cache) and a new governance gate to maintain.
- A baseline file must be kept honest as migrations land; a stale baseline is its own small rot risk
  (mitigated by requiring each entry to cite a tracking issue and by the gate failing on additions).
- Externalising the dynamic Reason prompt only covers its static template; the runtime-assembled
  portion stays in code and outside the file's review surface.

### Neutral

- No runtime behaviour change at proposal time — this ADR authorises the loader, format, and gate;
  the per-prompt migrations land as separate tracked PRs.
- Guardrail and injection-resistance instructions are unaffected: externalisation moves the text,
  it never weakens it (CLAUDE.md §3.3).

## Alternatives Considered

- **Keep prompts inline, registry-only.** Rejected — the registry governs in prose but cannot
  prevent a new inline prompt; the gap widens with every agent feature (the status quo this ADR
  exists to fix).
- **Big-bang migrate all three prompts in this change.** Rejected — violates one-reviewable-artifact
  (ADR-0060) and the AI-safety review surface; a per-prompt baseline lets the gate land first and
  migrations follow incrementally.
- **Store prompts in a DB / remote prompt service.** Rejected for the template — files in-repo keep
  prompts under the same review, diff, sign-off, and rollback discipline as code, with no new
  runtime dependency or availability risk.
- **Lint-only (no baseline), block all inline prompts immediately.** Rejected — would force the
  big-bang migration above before the loader is proven.

## Compliance & Risk

- **Controls affected:** OWASP LLM01 (prompt injection — text moves, guard unchanged), LLM08
  (excessive agency — prompts that shape agent actions become reviewable/versioned). See
  `specs/security/owasp-genai-control-matrix.yaml`.
- **Data classification impact:** none — prompt templates carry no PII (L4); the Reason prompt
  already states the context is PII-masked.
- **Autonomy impact:** none directly. No HITL/HOTL or feature-flag change (ADR-0015). The loader and
  gate touch `src/agents/` but **not** `src/agents/hitl_gateway.py` or `src/guardrails/`; the
  per-prompt migration PRs run the abuse-case suite per CLAUDE.md §3.2.
- **Review/expiry:** revisit once all three baseline prompts are migrated and the baseline is empty —
  at which point the gate flips to block _all_ inline prompts and this ADR moves to Accepted-fulfilled.

---

## Related

- `prompts/README.md` — target layout & front-matter schema (this ADR formalises it)
- `docs/ai/prompt-registry.md` — authoritative registry & change protocol
- `docs/ai/model-lifecycle.md` — model versions prompts pin to
- `src/agents/harness/planner.py` · `src/agents/harness/evaluator.py` · `src/agents/orchestrator/orchestrator.py` — current inline sources
- `scripts/governance/check_test_integrity.py` — baseline-gate pattern this gate follows
- CLAUDE.md §3.3 (AI governance), §3.6 (grounding & non-fabrication)
