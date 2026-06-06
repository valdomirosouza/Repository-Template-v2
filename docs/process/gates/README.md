# Phase Gate Contracts

Machine-readable projection of the 13-phase Agentic SDLC lifecycle
(`docs/process/WORKFLOW.md`). Agents and CI consume `phase-gates.yaml` to enforce
gates programmatically instead of parsing Markdown.

> **Source of truth:** `docs/process/WORKFLOW.md`. `phase-gates.yaml` MUST be kept
> in sync with it. When a phase, gate, or approval changes in WORKFLOW.md, update
> this YAML in the same PR.

**Spec:** Agentic-SDLC-Repository-Improvement-Directive.md §9 | **ADR:** ADR-0052, ADR-0054

---

## Why machine-readable

Before this file, phase gates lived only in prose. A human could read "Phase 6
prohibits deployment", but an agent could not query it. `phase-gates.yaml` lets an
agent answer, deterministically:

- _What phase is this feature in?_ (cross-referenced with `state.yaml`, see `docs/product/`)
- _Is `deploy` an allowed action right now?_ → check `phases[n].prohibited_agent_actions`
- _What must be true to exit this phase?_ → `phases[n].exit_criteria` + `required_*`

---

## Schema (`phase_gates_v1`)

Top-level keys:

| Key                 | Type   | Meaning                                        |
| ------------------- | ------ | ---------------------------------------------- |
| `schema_version`    | string | Contract version (`phase_gates_v1`)            |
| `source_of_truth`   | string | Path to the authoritative Markdown             |
| `roles`             | list   | Approval roles referenced by phases (see RACI) |
| `action_vocabulary` | list   | Canonical agent action verbs                   |
| `phases`            | list   | The 13 phase gate definitions                  |

Each entry in `phases`:

| Field                      | Type     | Meaning                                                            |
| -------------------------- | -------- | ------------------------------------------------------------------ |
| `id`                       | int 1–13 | Phase number                                                       |
| `name`                     | string   | Phase name                                                         |
| `primary_actor`            | string   | Role or `agent` that drives the phase                              |
| `required_artifacts`       | list     | Paths (with `{id}`/`{next}`/`{slug}` placeholders) that must exist |
| `required_approvals`       | list     | Roles whose approval is required to exit                           |
| `ci_checks`                | list     | CI workflow/job names that must be green                           |
| `blocking`                 | bool     | Whether failing the gate blocks progression                        |
| `allowed_agent_actions`    | list     | Actions an agent MAY take during this phase                        |
| `prohibited_agent_actions` | list     | Actions an agent MUST NOT take during this phase                   |
| `exit_criteria`            | string   | Human-readable summary of what "done" means                        |

Optional per-phase fields: `gate_checklist`, `coverage_min_percent`,
`prr_min_percent`, `requires_cab_approval`.

---

## Consumption contract

An agent determining whether it may perform an action:

1. Resolve the feature's `current_phase` from its `state.yaml` (`docs/product/FEAT-{id}/state.yaml`).
2. Look up that phase in `phase-gates.yaml`.
3. If the action is in `prohibited_agent_actions` → **refuse** (escalate per CLAUDE.md §14).
4. If the action is not in `allowed_agent_actions` → treat as prohibited (default-deny).
5. Real-world-effect actions still route through the runtime HITL gateway (ADR-0053) — phase gates are an _additional_ constraint, never a bypass.

Phase gates govern **process**; the runtime HITL/tool-registry enforcement
(ADR-0053) governs **execution**. Both apply.
