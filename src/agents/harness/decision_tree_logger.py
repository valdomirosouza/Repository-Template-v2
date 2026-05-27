"""DecisionTreeLogger — records agent decision bifurcations to the immutable audit log.

Spec: specs/ai/harness-design.md §9.1 (Decision Tree Logging)

Every branching decision made during sprint execution is logged with
action = "decision_bifurcation" so the full decision tree can be
reconstructed post-hoc from the audit log.
"""

from __future__ import annotations

from src.agents.harness.models import DecisionPoint
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger
from src.shared.models import AuditEvent

logger = get_logger("harness.decision_tree_logger")


class DecisionTreeLogger:
    """Records decision bifurcations for a single sprint execution.

    Writes each decision to the immutable audit log and keeps an
    in-memory list for inclusion in the ExecutionSummary.

    Usage::

        dt = DecisionTreeLogger(audit, agent_id="harness.coordinator", task_id=tid)
        await dt.log(
            decision_point="generation_strategy_iteration_1",
            options_considered=["fresh_generation", "feedback_incorporation"],
            option_chosen="fresh_generation",
            rationale="First attempt — no prior feedback available.",
        )
        decisions = dt.get_decisions()
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        agent_id: str,
        task_id: str,
    ) -> None:
        self._audit = audit_logger
        self._agent_id = agent_id
        self._task_id = task_id
        self._decisions: list[DecisionPoint] = []

    async def log(
        self,
        decision_point: str,
        options_considered: list[str],
        option_chosen: str,
        rationale: str,
        trace_id: str | None = None,
    ) -> DecisionPoint:
        """Record a decision bifurcation and write it to the audit log.

        Returns the persisted DecisionPoint.
        """
        dp = DecisionPoint(
            decision_point=decision_point,
            options_considered=options_considered,
            option_chosen=option_chosen,
            rationale=rationale,
        )
        self._decisions.append(dp)

        await self._audit.log_event(
            AuditEvent(
                event_type="agent.decision.bifurcation",
                agent_id=self._agent_id,
                action="decision_bifurcation",
                outcome="EXECUTED",
                metadata={
                    "task_id": self._task_id,
                    "decision_point": decision_point,
                    "options_considered": options_considered,
                    "option_chosen": option_chosen,
                    "rationale": rationale,
                },
                trace_id=trace_id,
            )
        )

        logger.info(
            "Decision bifurcation recorded",
            decision_point=decision_point,
            option_chosen=option_chosen,
            task_id=self._task_id,
        )

        return dp

    def get_decisions(self) -> list[DecisionPoint]:
        """Return all decisions recorded so far (ordered chronologically)."""
        return list(self._decisions)
