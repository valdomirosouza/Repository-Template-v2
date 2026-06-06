# ADR-0041: Context Graph — Autonomy Tier

**Status:** Accepted
**Date:** 2026-06-05
**Author:** Valdomiro Souza
**Issue:** #18
**Related ADRs:** ADR-0011 (HITL/HOTL), ADR-0015 (Feature Flag Strategy), ADR-0017 (Agent Memory Architecture), ADR-0037 (Governance Gate), ADR-0038 (Learn Stage), ADR-0040 (Maturity Model)

---

## Context

Gartner names "context graphs" as the enabling mechanism for the Autonomy maturity
tier (Level 4). Two gaps were identified in the Gartner Agentic AI Compliance gap
analysis (2026-06-05):

- **A1** — No context graph: `src/memory/` has session memory and vector store but
  no structured goal-state graph. Long-horizon tasks have no durable representation
  of "what has been decided, what remains, and why."

- **A2** — No Autonomy-tier prerequisite guard: the existing `autonomous-mode` flag
  moves from HITL to HOTL but does not enforce that the Learn stage is active and a
  context graph is available. An agent operating at HOTL without these prerequisites
  is ungoverned automation — exactly the pattern that causes the 40% project
  cancellation rate.

---

## Decision

**Context Graph (`src/agents/context_graph.py`):**

Introduce a `ContextGraph` class that models the agent's evolving goal state across
sessions:

- `GoalState` — root goal + sub-goals with status lifecycle (active/completed/blocked/abandoned)
- `Constraint` — time, resource, and compliance constraints
- `GatheredContext` — source references with relevance scores
- `Decision` — rationale + ADR reference for decisions made during the session

All state is serialisable via `to_dict()` / `from_dict()` for PostgreSQL persistence
(JSONB column in `agent_context_graphs` table — migration `0006`).

`to_prompt_block()` renders a compact `[CONTEXT_GRAPH]` block that can be injected
into the Reason-stage LLM system prompt alongside the `[PRECEDENTS]` block from
ADR-0038.

**Autonomy-Tier Prerequisites Guard (`src/shared/feature_flags.py`):**

`is_autonomy_tier_ready()` checks the `autonomy-tier-ready` flag and, if enabled,
validates all prerequisites before returning `True`. Raises `AutonomyPrerequisiteError`
if any prerequisite is unmet:

1. `learning-mode` flag is `active`
2. `src/agents/context_graph.py` is present

The `autonomy-tier-ready.yaml` flag defaults to `false`. Enabling it requires the
`governance-council-approved` label on the PR (enforced by ADR-0037 governance gate).

---

## Consequences

**Positive:**

- Completes the prerequisites for Gartner Level 4 Autonomy — the maturity check
  script (`make agentic-maturity-check`) now shows all criteria available
- `AutonomyPrerequisiteError` prevents ungoverned escalation to full autonomy
- `to_prompt_block()` gives the LLM persistent cross-session goal state without
  requiring the full conversation history to be re-loaded

**Negative:**

- PostgreSQL persistence is in the migration but the `ContextGraph` class does
  not yet wire the DB save/load — production deployments must add a repository
  layer. In-process instances reset on restart.
- `is_autonomy_tier_ready()` does not query the DB to verify table reachability
  at flag-check time; that check should be added when the DB repository layer
  is implemented.

**Neutral:**

- `from_dict()` / `to_dict()` enable unit testing without any infrastructure
- The Alembic migration follows the existing pattern (revision 0006 → 0005)

---

## Alternatives Considered

- **Reuse `src/memory/session_memory.py`:** Session memory is a key-value store
  per session. Rejected — no structured goal tree, no sub-goal lifecycle, no
  cross-session persistence design.

- **JSON file on disk:** Simpler than PostgreSQL for local dev.
  Rejected — does not scale to multi-instance deployments; not ACID-safe.
