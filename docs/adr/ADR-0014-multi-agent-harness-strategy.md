# ADR-0014 — Multi-Agent Harness Strategy

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** AI Lead, Tech Lead

---

## Context

The existing single-agent orchestrator (`src/agents/orchestrator/orchestrator.py`) implements a
Perception → Reason → Act loop adequate for short, well-defined tasks. Empirical evidence from
Anthropic Engineering ("Harness Design for Long-Running Application Development", 2025) and
internal observation identifies two systematic failure modes when tasks grow in duration or
complexity:

**1. Quality plateau:** A single agent asked to self-evaluate its own output consistently
over-rates quality. Models "respond by confidently praising the work" even when the result
is incomplete or mediocre. Self-criticism prompts improve results modestly but plateau quickly.

**2. Context window failure:** Multi-hour tasks exceed the effective context window in two
distinct ways: (a) _context exhaustion_ — the model loses coherence as the window fills with
prior turns; (b) _context anxiety_ — the model prematurely wraps up work when it perceives
the context limit approaching, even if capable of continuing.

The current P→R→A loop has no mechanism to address either failure mode. It is also
unstructured for multi-step tasks: there is no formal specification of what constitutes
a completed sub-task, no external quality gate, and no strategy for transferring state
across context boundaries.

---

## Decision

Adopt a **configurable multi-agent harness** layered above the existing orchestrator,
implemented in `src/agents/harness/`. The harness introduces three specialised agents:

### Planner Agent

Converts a brief user description (1–4 sentences) into a detailed `ProductSpec`
and a list of `SprintContract` objects. Each sprint contract defines:

- `objectives` — what the user will experience (non-technical)
- `success_criteria` — independently testable, binary (pass / fail)

The planner avoids technical over-specification: it defines _what_, not _how_.

### Generator Agent

Receives a single `SprintContract` and produces `GeneratorArtifact` outputs.
Operates within the existing P→R→A loop. Negotiates the sprint contract with
the evaluator before beginning implementation.

### Evaluator Agent

Receives a `SprintContract` and a `GeneratorArtifact`. Scores the output on
four dimensions (quality, originality, craft, functionality). Operates with
explicit skepticism: its default assumption is that the implementation is
incomplete or has defects. It tests each `success_criteria` independently —
it does not infer correctness from reading code alone.

### Harness Coordinator

Routes tasks to one of three modes, selected via `settings.harness_mode`:

| Mode         | Agents active                   | Use case                                      |
| ------------ | ------------------------------- | --------------------------------------------- |
| `solo`       | Orchestrator P→R→A only         | Simple, single-step tasks                     |
| `simplified` | Generator + Evaluator           | Feature-level tasks; removes planner overhead |
| `full`       | Planner + Generator + Evaluator | Complex, multi-hour, multi-feature tasks      |

### Context Manager

At every inter-agent boundary, `ContextManager` decides between two strategies:

- **Compaction:** structured summarisation; continuity preserved (intra-agent default)
- **Reset:** context window cleared; structured `ContextSnapshot` passed as handoff
  (triggered when window utilisation ≥ `settings.harness_context_reset_threshold`)

### Sprint Contracts

Sprint contracts are negotiated between Generator and Evaluator _before_ implementation
begins. This prevents the generator from building features that the evaluator cannot
verify, and prevents the evaluator from applying criteria that were not agreed upon.

### Escalation to HITL

If the evaluator scores below `settings.harness_evaluator_pass_threshold` after
`settings.harness_max_iterations` retries, the harness escalates to the HITL gateway.
A human reviewer sees the sprint contract, the final artifact, and the evaluator feedback.

---

## Consequences

### Positive

- External evaluation eliminates self-praise bias; quality gates are structurally enforced
- Sprint contracts make each implementation step verifiable before and after execution
- Context manager prevents context exhaustion and context anxiety on long-running tasks
- `harness_mode = "solo"` preserves the existing low-overhead path for simple tasks
- As model capability improves, individual harness components can be disabled without
  restructuring (principle: strip load-bearing pieces as they cease to carry load)
- Escalation to HITL on harness failure closes the human oversight gap for complex tasks

### Negative / Trade-offs

- Cost: empirical data shows full harness costs approximately 22× more than solo
  ($200 vs $9 for equivalent task in Anthropic Engineering study); justified only for
  tasks beyond solo capability
- Latency: full harness runs may take 2–6 hours; not suitable for synchronous user flows
- Harness components must be maintained; evaluator prompt requires ongoing tuning as
  model behaviour evolves
- Sprint decomposition adds planning overhead; degenerate for tasks that are truly simple

---

## Alternatives Considered

**Single agent with self-critique loop**
Evaluated first. Self-critique prompts ("review your own output and improve it") produce
marginal gains before plateauing. The model cannot reliably identify its own blind spots.
Rejected because the quality ceiling is lower than an external evaluator and the mechanism
provides no new information — the generator and critic share the same weights and context.

**Off-the-shelf multi-agent framework (LangGraph, AutoGen)**
Rejected for the same reasons as ADR-0010: framework abstractions obscure the Act step,
making HITL integration dependent on internal callbacks. The harness requires explicit
control over every agent boundary for audit compliance.

**Always-on full harness (no mode selection)**
Rejected: the 22× cost multiplier makes full harness economically inviable for simple
tasks. Mode selection (`solo` / `simplified` / `full`) allows the system to apply the
minimum necessary harness for a given task complexity.
