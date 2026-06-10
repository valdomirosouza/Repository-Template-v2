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

## Durable `STATE` vs transient `HANDOFF`

The handoff message and shared-state JSON above are **transient**: they checkpoint "where we are,
what's next" and are overwritten as the pipeline advances. They are deliberately **small — target
≈ 500 tokens** for the resume checkpoint (`notes` is a summary, not a transcript) so a pause/resume
re-hydrates cheaply within the per-phase context budget (`docs/process/context-budget.md`).

**Durable** knowledge — decisions, blockers, and lessons that must survive across sessions — does
**not** belong here. It accretes in the typed-ID State Ledger (`AD-NNN` / `B-NNN` / `L-NNN`,
Deferred Ideas, Todos) defined in `specs/ai/agent-memory.md §5b`, which self-prunes (🟢/🟡/🔴,
archive > 60 days). Cite ledger entries from a handoff's `notes` by ID (e.g. `"see L-007"`) rather
than inlining them — that keeps the checkpoint tiny while preserving the durable trail.

---

## Sub-agent context contract (receive / return envelope)

A phase agent runs in **isolated context** — it does not inherit the orchestrator's session. To
keep delegation cheap and the FINAL-REPORT mechanical, both ends of the exchange are fixed: a
**narrow input allow-list** in, a **fixed structured object** out.

### Receives — allow-list (nothing outside it)

A phase agent is briefed with **only**:

- its **phase brief** — `PHASE`, `SPEC`, `SLUG`, `MODE`, `TIER`, `LANGUAGE`, `BACKLOG_IDS`,
  `GOVERNING_ADRS`, `GATE_CRITERIA` (see `.claude/skills/deliver/SKILL.md`);
- the **referenced spec/design section(s) in scope** for this phase (not the whole spec corpus);
- **`CONVENTIONS` + the ≤ 2 phase skills** (ADR-0060) + `skills/engineering/testing-strategy.md`
  for test phases;
- the phase's **`base_load`** from `docs/process/context-budget.md`.

It is **not** given: other phases' task definitions, the orchestrator's chat history, the durable
`STATE.md` ledger (it may be handed _specific_ `AD-/B-/L-NNN` entries by ID if relevant), or
unrelated specs. Context minimalism is the token goal (`CLAUDE.md §13`).

### Returns — fixed envelope (the orchestrator parses this)

```json
{
  "status": "done | blocked | failed",
  "phase": 6,
  "files_changed": ["src/...", "tests/..."],
  "gate": {
    "result": "PASS | FAIL | N-A | BLOCKED | SIMULATED | WAIVED",
    "counts": { "tests": 0, "coverage_pct": 0 }
  },
  "spec_deviations": ["SPEC_DEVIATION: <what> / Reason: <why>"],
  "issues": ["anything the orchestrator/human must decide"],
  "human_gate": false,
  "wall_clock": { "start": "ISO-8601", "end": "ISO-8601" }
}
```

| Field             | Meaning                                                                                  |
| ----------------- | ---------------------------------------------------------------------------------------- |
| `status`          | `done` \| `blocked` (missing input/approval) \| `failed` (a required gate failed)        |
| `files_changed`   | real paths in CODE; `reports/<slug>/…` in DRY-RUN                                        |
| `gate`            | gate `result` **plus counts** (tests run, coverage %, findings) — feeds the FINAL-REPORT |
| `spec_deviations` | open `SPEC_DEVIATION` markers introduced this phase (WI-04; surfaced for §7 mapping)     |
| `issues`          | problems/risks for the orchestrator or human                                             |
| `human_gate`      | `true` ⇒ orchestrator STOPs for human approval before the next phase                     |
| `wall_clock`      | start/end timestamps → agent wall-clock vs human-equiv in the FINAL-REPORT               |

This **refines** the inter-phase handoff message above: the handoff message is the routing signal
between agents; this envelope is the executor's full structured return that the orchestrator parses
to update traceability and decide the next step. A fixed return is what makes FINAL-REPORT
generation mechanical rather than free-text parsing.

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
