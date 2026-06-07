# Delivery Agent Handoff Schema

> **Version:** 1.0.0 | **ADR:** ADR-0058 | **Spec:** `docs/sdlc/agentic-spec-driven-delivery.md`

This defines the contract that the Claude Code **delivery agents** (`.claude/agents/`)
use to communicate as a feature moves through the 15-phase
[Agentic Spec-Driven Delivery Workflow](agentic-spec-driven-delivery.md). One
orchestrator sequences 15 phase agents (Phase 0–14); each agent validates its inputs,
does exactly one phase, persists its artifact, and emits a **handoff message**.

> **These are dev-time delivery subagents** that _operate_ the SDLC (run via the
> Claude Code CLI). They are distinct from the runtime product agents in `src/agents/`
> (the deployed application's HITL/HOTL orchestrator, guardrails, tool registry).

---

## Handoff message

Every phase agent emits exactly one handoff message and then stops:

```json
{
  "status": "done | blocked",
  "phase": 0,
  "agent": "asdd-phase-0-intake",
  "artifacts": ["intake-form.md"],
  "handoff_to": "asdd-phase-1-conception",
  "reason": "",
  "notes": "Risk class: normal feature; owner: @alice",
  "human_gate": false,
  "timestamp": "2026-06-06T00:00:00+00:00"
}
```

| Field        | Type                    | Meaning                                                                        |
| ------------ | ----------------------- | ------------------------------------------------------------------------------ |
| `status`     | `"done"` \| `"blocked"` | `blocked` halts the pipeline                                                   |
| `phase`      | int 0–14                | The phase this agent executed                                                  |
| `agent`      | string                  | The emitting agent's name                                                      |
| `artifacts`  | string[]                | Paths to artifacts produced/updated this phase                                 |
| `handoff_to` | string                  | Next agent, or `"none (terminal)"`                                             |
| `reason`     | string                  | **Required when `blocked`** — why it halted                                    |
| `notes`      | string                  | Free-text summary for the orchestrator/human                                   |
| `human_gate` | bool                    | `true` ⇒ a **mandatory human approval** is required before the next phase runs |
| `timestamp`  | ISO-8601                | When the handoff was emitted                                                   |

**Validation rules** (enforced by `scripts/asdd_state.py`, fail-closed): `status` in the
enum, `phase` ∈ [0, 14], `agent` non-empty, `artifacts` a list, `handoff_to` present,
`reason` present when `blocked`.

---

## Shared state / context object

The orchestrator maintains one shared context per feature at
`.agent/delivery/<feature_id>/state.json` (gitignored — per-run delivery state):

```json
{
  "schema_version": "asdd_state_v1",
  "feature_id": "FEAT-42",
  "title": "Bulk HITL approval",
  "risk_class": "normal feature",
  "current_phase": 0,
  "blocked": false,
  "started_at": "2026-06-06T00:00:00+00:00",
  "updated_at": "2026-06-06T00:00:00+00:00",
  "artifacts": { "intake-form.md": "docs/product/FEAT-42/intake-form.md" },
  "handoffs": [{ "...": "one entry per phase" }]
}
```

Helper (called by agents via Bash):

```bash
python scripts/asdd_state.py init --feature FEAT-42 --title "..." --risk-class "normal feature"
python scripts/asdd_state.py append-handoff --feature FEAT-42 --status done --phase 0 \
    --agent asdd-phase-0-intake --artifacts intake-form.md \
    --handoff-to asdd-phase-1-conception --notes "..."
python scripts/asdd_state.py show --feature FEAT-42
```

---

## Governance (non-negotiable)

The delivery agents follow the workflow's core principle — _agents draft, analyze,
test, explain, recommend; humans approve, own, operate_:

1. **Validate inputs first.** If a required artifact/approval is missing, emit
   `status: "blocked"` with a `reason` and **halt** — do not improvise.
2. **Stop at mandatory human gates.** A phase that crosses a human-approval boundary
   emits `human_gate: true`; the orchestrator pauses for human approval and does **not**
   auto-proceed. The nine gates are listed in the canonical reference.
3. **No autonomous real-world effects.** Agents never merge PRs, deploy, cut releases,
   or change autonomy flags on their own. The Release/Production agents **prepare and
   recommend** (validate readiness, produce the plan); a human executes the irreversible
   step (CLAUDE.md §3.3, ADR-0011/0053).
4. **Risk-based.** The orchestrator skips phases that don't apply to the feature's
   `risk_class` (e.g., the AI Safety phase runs only for AI/LLM/agentic changes).

See `.claude/agents/README.md` for the agent roster and how to run the system.
