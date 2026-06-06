# Spec: Context Graph — Autonomy Tier

**Status:** Approved
**Issue:** #18 | **ADR:** ADR-0041
**Owner:** AI Governance Lead | **Last updated:** 2026-06-05

---

## 1. Purpose

Enable the **Autonomy** maturity tier (Gartner Level 4) by providing a durable,
structured representation of an agent's evolving goal state across multiple sessions.
Without a context graph, long-horizon tasks have no persistent record of "what has
been decided, what remains, and why" — each session re-derives context from scratch.

---

## 2. Data Model

### Goal State

```json
{
  "goal_id": "<uuid>",
  "description": "Migrate payment service to new API",
  "status": "active | completed | blocked | abandoned",
  "parent_id": "<uuid> | null",
  "created_at": "<ISO-8601>",
  "updated_at": "<ISO-8601>"
}
```

### `ContextGraph` (top-level)

```json
{
  "graph_id": "<uuid>",
  "session_id": "<session_id>",
  "root_goal": "<goal_state>",
  "sub_goals": ["<goal_state>", "..."],
  "constraints": [{ "type": "time|resource|compliance", "value": "..." }],
  "gathered_context": [
    {
      "source": "...",
      "content_hash": "...",
      "relevance_score": 0.0,
      "retrieved_at": "..."
    }
  ],
  "decisions_made": [
    {
      "decision_id": "...",
      "rationale": "...",
      "adr_reference": "...",
      "made_at": "..."
    }
  ],
  "created_at": "<ISO-8601>",
  "updated_at": "<ISO-8601>"
}
```

Schema is JSON-LD compatible. Stored in PostgreSQL as a `JSONB` column in the
`agent_context_graphs` table (migration: `0006_add_context_graph_table.py`).

---

## 3. API

```python
class ContextGraph:
    def add_sub_goal(self, description: str) -> str          # returns sub_goal_id
    def mark_complete(self, goal_id: str) -> None
    def mark_blocked(self, goal_id: str) -> None
    def add_constraint(self, type: str, value: str) -> None
    def add_gathered_context(self, source: str, content_hash: str, relevance_score: float) -> None
    def add_decision(self, rationale: str, adr_reference: str = "") -> str  # returns decision_id
    def to_prompt_block(self) -> str   # renders compact [CONTEXT_GRAPH] block for LLM injection
    def to_dict(self) -> dict          # full serialisation for PostgreSQL persistence
```

---

## 4. `[CONTEXT_GRAPH]` Prompt Block

```
[CONTEXT_GRAPH]
goal: Migrate payment service to new API (active)
sub_goals:
  ✅ Audit current API usage
  🔄 Update client libraries (active)
  ⬜ Update integration tests
constraints:
  - compliance: must not expose PII in logs
decisions:
  - Use adapter pattern to preserve backward compat (ADR-0024)
[/CONTEXT_GRAPH]
```

---

## 5. Autonomy-Tier Prerequisites Guard

The `autonomy-tier-ready` flag **must not** be enabled unless all prerequisites
are confirmed:

| Prerequisite                     | Check                                              |
| -------------------------------- | -------------------------------------------------- |
| `learning-mode` flag is `active` | `get_learning_mode() == "active"`                  |
| Context graph table reachable    | DB ping + table existence check                    |
| Governance council sign-off      | `governance-council-approved` label on enabling PR |

`get_autonomy_level()` in `feature_flags.py` raises `AutonomyPrerequisiteError`
if `autonomy-tier-ready` is enabled but any prerequisite is unmet.

---

## 6. Related

- `src/agents/context_graph.py` — implementation
- `alembic/versions/0006_add_context_graph_table.py` — migration
- `infrastructure/feature-flags/flags/autonomy-tier-ready.yaml` — guard flag
- `src/shared/feature_flags.py` — `AutonomyPrerequisiteError`
- `docs/adr/ADR-0041-context-graph-autonomy-tier.md`
