"""Compensation registry — maps actions to their compensating (undo) actions.

HOTL (Human On The Loop) lets low-risk reversible actions execute immediately,
subject to a human override window. If a reviewer overrides within the window, the
system attempts the action's *compensating action* to undo the effect. This registry
is the lookup layer over the tool catalog's reversibility metadata (ADR-0055).

Policy (fail-closed):
  - An action is reversible only if its tool declares ``reversible: true``.
  - A non-reversible action MUST NOT run autonomously under HOTL — it requires
    explicit human approval (HITL). ``can_run_under_hotl`` returns False for it.
  - An action may run under HOTL only when reversible AND its computed risk score
    is at or below the tool's ``max_hotl_risk_score``.

Spec: specs/ai/hitl-hotl.md (HOTL Specification, Override Procedure)
ADR:  ADR-0055 (HOTL operationalization), ADR-0011
"""

from __future__ import annotations

from src.agents.tool_registry import ToolRegistry, default_tool_registry
from src.observability.logger import get_logger

logger = get_logger("compensation_registry")


class CompensationRegistry:
    """Reversibility + compensation lookups for agent actions.

    Backed by the tool registry so reversibility metadata has a single source of
    truth (tools.yaml). Action names are normalized (underscores → hyphens).
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or default_tool_registry

    def is_reversible(self, action_type: str) -> bool:
        """Return True if the action's tool declares itself reversible."""
        return self._registry.is_reversible(action_type)

    def get_compensating_action(self, action_type: str) -> str | None:
        """Return the compensating action name for an action, or None."""
        return self._registry.compensating_action(action_type)

    def has_compensating_action(self, action_type: str) -> bool:
        """Return True if a compensating action is declared for this action."""
        return self.get_compensating_action(action_type) is not None

    def can_run_under_hotl(self, action_type: str, risk_score: float) -> tuple[bool, str]:
        """Return (allowed, reason) for autonomous HOTL execution of an action.

        Fail-closed: unregistered or non-reversible actions are never allowed under
        HOTL — they must route through HITL for explicit human approval.
        """
        if not self._registry.is_registered(action_type):
            return False, f"action '{action_type}' is not a registered tool"
        if not self.is_reversible(action_type):
            return False, (
                f"action '{action_type}' is non-reversible — HOTL requires explicit "
                "human approval (HITL)"
            )
        ceiling = self._registry.max_hotl_risk_score(action_type)
        if risk_score > ceiling:
            return False, (
                f"risk_score {risk_score:.3f} exceeds the tool's max HOTL risk "
                f"score ({ceiling:.3f})"
            )
        return True, "reversible and within HOTL risk ceiling"
