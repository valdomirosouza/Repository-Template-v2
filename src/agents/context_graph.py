"""Context graph — durable goal-state representation for the Autonomy maturity tier.

Spec:  specs/ai/context-graph.md
ADR:   ADR-0041
Issue: #18

Enables Gartner Level 4 (Autonomy) by persisting the agent's evolving goal state,
sub-goals, constraints, gathered context, and decisions across multiple sessions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ── Sub-models ────────────────────────────────────────────────────────────────


@dataclass
class GoalState:
    description: str
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "active"  # active | completed | blocked | abandoned
    parent_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "status": self.status,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Constraint:
    type: str  # time | resource | compliance
    value: str


@dataclass
class GatheredContext:
    source: str
    content_hash: str
    relevance_score: float
    retrieved_at: str = field(default_factory=_now)


@dataclass
class Decision:
    rationale: str
    adr_reference: str = ""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    made_at: str = field(default_factory=_now)


# ── ContextGraph ──────────────────────────────────────────────────────────────


class ContextGraph:
    """Structured, durable representation of an agent's goal state.

    Designed for PostgreSQL persistence (JSONB) via `to_dict()` / `from_dict()`.
    In local dev and tests, instances are in-process only.

    Usage::

        graph = ContextGraph(session_id="sess-123", root_description="Migrate API")
        sub_id = graph.add_sub_goal("Audit current usage")
        graph.mark_complete(sub_id)
        block = graph.to_prompt_block()
    """

    def __init__(self, session_id: str, root_description: str) -> None:
        self.graph_id = str(uuid.uuid4())
        self.session_id = session_id
        self.root_goal = GoalState(description=root_description)
        self._sub_goals: dict[str, GoalState] = {}
        self._constraints: list[Constraint] = []
        self._gathered_context: list[GatheredContext] = []
        self._decisions: list[Decision] = []
        self.created_at = _now()
        self.updated_at = _now()

    # ── Mutations ─────────────────────────────────────────────────────────────

    def add_sub_goal(self, description: str) -> str:
        """Add a sub-goal under the root goal. Returns the new sub_goal_id."""
        sg = GoalState(description=description, parent_id=self.root_goal.goal_id)
        self._sub_goals[sg.goal_id] = sg
        self._touch()
        return sg.goal_id

    def mark_complete(self, goal_id: str) -> None:
        """Mark a goal or sub-goal as completed."""
        self._set_status(goal_id, "completed")

    def mark_blocked(self, goal_id: str) -> None:
        """Mark a goal or sub-goal as blocked."""
        self._set_status(goal_id, "blocked")

    def add_constraint(self, type: str, value: str) -> None:
        self._constraints.append(Constraint(type=type, value=value))
        self._touch()

    def add_gathered_context(self, source: str, content_hash: str, relevance_score: float) -> None:
        self._gathered_context.append(
            GatheredContext(
                source=source,
                content_hash=content_hash,
                relevance_score=relevance_score,
            )
        )
        self._touch()

    def add_decision(self, rationale: str, adr_reference: str = "") -> str:
        """Record a decision made during this session. Returns decision_id."""
        d = Decision(rationale=rationale, adr_reference=adr_reference)
        self._decisions.append(d)
        self._touch()
        return d.decision_id

    # ── Rendering ─────────────────────────────────────────────────────────────

    def to_prompt_block(self) -> str:
        """Render a compact [CONTEXT_GRAPH] block for LLM injection."""
        _status_icon = {
            "completed": "✅",
            "active": "🔄",
            "blocked": "🚫",
            "abandoned": "❌",
        }
        lines = ["[CONTEXT_GRAPH]"]
        lines.append(f"goal: {self.root_goal.description} ({self.root_goal.status})")

        if self._sub_goals:
            lines.append("sub_goals:")
            for sg in self._sub_goals.values():
                icon = _status_icon.get(sg.status, "⬜")
                lines.append(f"  {icon} {sg.description}")

        if self._constraints:
            lines.append("constraints:")
            for c in self._constraints:
                lines.append(f"  - {c.type}: {c.value}")

        if self._decisions:
            lines.append("decisions:")
            for d in self._decisions:
                ref = f" ({d.adr_reference})" if d.adr_reference else ""
                lines.append(f"  - {d.rationale}{ref}")

        lines.append("[/CONTEXT_GRAPH]")
        return "\n".join(lines)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "session_id": self.session_id,
            "root_goal": self.root_goal.to_dict(),
            "sub_goals": [sg.to_dict() for sg in self._sub_goals.values()],
            "constraints": [{"type": c.type, "value": c.value} for c in self._constraints],
            "gathered_context": [
                {
                    "source": gc.source,
                    "content_hash": gc.content_hash,
                    "relevance_score": gc.relevance_score,
                    "retrieved_at": gc.retrieved_at,
                }
                for gc in self._gathered_context
            ],
            "decisions_made": [
                {
                    "decision_id": d.decision_id,
                    "rationale": d.rationale,
                    "adr_reference": d.adr_reference,
                    "made_at": d.made_at,
                }
                for d in self._decisions
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextGraph:
        root = data["root_goal"]
        graph = cls(
            session_id=data["session_id"],
            root_description=root["description"],
        )
        graph.graph_id = data["graph_id"]
        graph.root_goal.goal_id = root["goal_id"]
        graph.root_goal.status = root["status"]
        graph.root_goal.created_at = root["created_at"]
        graph.root_goal.updated_at = root["updated_at"]

        for sg in data.get("sub_goals", []):
            goal = GoalState(
                description=sg["description"],
                goal_id=sg["goal_id"],
                status=sg["status"],
                parent_id=sg.get("parent_id"),
                created_at=sg["created_at"],
                updated_at=sg["updated_at"],
            )
            graph._sub_goals[goal.goal_id] = goal

        for c in data.get("constraints", []):
            graph._constraints.append(Constraint(type=c["type"], value=c["value"]))

        for gc in data.get("gathered_context", []):
            graph._gathered_context.append(
                GatheredContext(
                    source=gc["source"],
                    content_hash=gc["content_hash"],
                    relevance_score=gc["relevance_score"],
                    retrieved_at=gc["retrieved_at"],
                )
            )

        for d in data.get("decisions_made", []):
            dec = Decision(
                rationale=d["rationale"],
                adr_reference=d.get("adr_reference", ""),
                decision_id=d["decision_id"],
                made_at=d["made_at"],
            )
            graph._decisions.append(dec)

        graph.created_at = data["created_at"]
        graph.updated_at = data["updated_at"]
        return graph

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _touch(self) -> None:
        self.updated_at = _now()

    def _set_status(self, goal_id: str, status: str) -> None:
        if goal_id == self.root_goal.goal_id:
            self.root_goal.status = status
            self.root_goal.updated_at = _now()
        elif goal_id in self._sub_goals:
            self._sub_goals[goal_id].status = status
            self._sub_goals[goal_id].updated_at = _now()
        else:
            raise KeyError(f"Goal '{goal_id}' not found in context graph")
        self._touch()
