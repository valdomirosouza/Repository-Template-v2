"""Context management strategy: compaction vs reset for long-running harness sessions.

Spec: specs/ai/harness-design.md §3 (Context Management Strategy)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Two failure modes addressed:
  - Context exhaustion: model loses coherence as window fills.
  - Context anxiety: model prematurely wraps up approaching perceived limits.

Strategy:
  - Compaction (intra-agent): structured summary, continuity preserved.
  - Reset (inter-agent boundary): clear window + ContextSnapshot handoff.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agents.harness.models import ContextSnapshot
from src.guardrails.pii_filter import mask_dict
from src.observability.logger import get_logger

logger = get_logger("harness.context_manager")

_MAX_KEY_DECISIONS = 20
_MAX_DECISION_LEN = 200

_RESTORE_TEMPLATE = """\
You are resuming a task. Here is the context summary from the previous session:

Task ID: {task_id}
Last completed sprint: {last_sprint_id}

Key decisions made so far:
{decisions}

Current state:
{masked_state}

Continue from where the previous context left off. Do not re-explain prior decisions.
"""


class ContextManager:
    """Decides when to reset context and builds structured handoff snapshots.

    Spec: specs/ai/harness-design.md §3
    """

    def __init__(self, reset_threshold: float = 0.85) -> None:
        self._threshold = reset_threshold

    def should_reset(self, utilisation: float) -> bool:
        """Return True when context window utilisation meets or exceeds the threshold."""
        return utilisation >= self._threshold

    def create_snapshot(
        self,
        agent_id: str,
        task_id: str,
        masked_state: dict[str, Any],
        key_decisions: list[str] | None = None,
        last_sprint_id: str | None = None,
    ) -> ContextSnapshot:
        """Build a ContextSnapshot for handoff after a context reset.

        Caller MUST pass already-masked state — this method does not run PII
        filter itself to avoid double-masking, but applies it as a safety net.
        """
        safe_state = mask_dict(masked_state)

        decisions = (key_decisions or [])[:_MAX_KEY_DECISIONS]
        decisions = [d[:_MAX_DECISION_LEN] for d in decisions]

        snapshot = ContextSnapshot(
            agent_id=agent_id,
            created_at=datetime.now(UTC).isoformat(),
            task_id=task_id,
            last_sprint_id=last_sprint_id,
            key_decisions=decisions,
            masked_state=safe_state,
        )

        logger.info(
            "Context snapshot created",
            agent_id=agent_id,
            task_id=task_id,
            last_sprint_id=last_sprint_id,
            decision_count=len(decisions),
        )

        return snapshot

    def restore_prompt(self, snapshot: ContextSnapshot) -> str:
        """Render a compact resume prompt to inject as system message after a reset."""
        decisions_text = (
            "\n".join(f"  - {d}" for d in snapshot.key_decisions) or "  (none recorded)"
        )

        import json

        state_text = json.dumps(snapshot.masked_state, indent=2) if snapshot.masked_state else "{}"

        return _RESTORE_TEMPLATE.format(
            task_id=snapshot.task_id,
            last_sprint_id=snapshot.last_sprint_id or "none",
            decisions=decisions_text,
            masked_state=state_text,
        )
