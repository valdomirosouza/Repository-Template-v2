# AI Agents Module — Optional Extension

> **This module is opt-in.** Projects that do not need AI agents, LLM pipelines, or
> autonomous workflows can delete this entire directory (`src/agents/`) along with
> `src/guardrails/`, `src/memory/`, `specs/ai/`, and `docs/ai-governance/`.
>
> For the full removal checklist and activation guide see:
> [`docs/optional-extensions/ai-agents/README.md`](../../docs/optional-extensions/ai-agents/README.md)

---

## What this module provides

| Component           | File                  | Purpose                                                                             |
| ------------------- | --------------------- | ----------------------------------------------------------------------------------- |
| HITL Gateway        | `hitl_gateway.py`     | Blocks consequential actions until a human approves                                 |
| HITL Store          | `hitl_store.py`       | Pluggable persistence for pending approvals (Redis / Memory)                        |
| Agent Orchestrator  | `orchestrator/`       | Perception → Reason → Act loop driving the LLM pipeline                             |
| Multi-Agent Harness | `harness/`            | Planner → Generator → Evaluator wrapper (optional, opt-out via `harness_mode=solo`) |
| Risk Scorer         | `risk_scorer.py`      | Deterministic 5-factor risk score; overrides LLM-provided score                     |
| Request Store       | `request_store.py`    | Pluggable request state (Redis / Memory)                                            |
| Feedback Loop       | `feedback_loop.py`    | Agent self-improvement via evaluator signals                                        |
| Sandbox Executor    | `sandbox_executor.py` | Executes agent-generated code in an isolated environment                            |

## Governance

When this module is active, these rules are **mandatory** (see `CLAUDE.md §3.3`):

- All agent actions with real-world effects must route through `hitl_gateway.py`.
- Agent-generated code must run in `sandbox_executor.py` with explicit HITL approval.
- Every agent action must be logged via `src/guardrails/audit_logger.py`.
- HOTL (autonomous) mode requires ADR-0015 governance sign-off.

## Relevant ADRs

ADR-0010 · ADR-0011 · ADR-0014 · ADR-0015 · ADR-0016 · ADR-0017
