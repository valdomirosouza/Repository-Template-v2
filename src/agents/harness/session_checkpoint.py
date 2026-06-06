"""Durable session checkpoint for long-running agentic tasks.

Spec: specs/ai/long-running-session.md
ADR:  ADR-0033 (Long-Running Agent Session Durability)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.agents.harness.models import ProductSpec
from src.observability.logger import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aredis

logger = get_logger("harness.session_checkpoint")

_REDIS_KEY_PREFIX = "session:checkpoint:"
_REDIS_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_LOCAL_CHECKPOINT_DIR = Path(".claude/checkpoints")


@dataclass
class SessionCheckpoint:
    """Full state needed to resume a sprint across session boundaries.

    Spec: specs/ai/long-running-session.md §2
    """

    session_id: str
    task_id: str
    sprint_plan: ProductSpec
    current_step: int = 0
    completed_steps: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())
    correlation_id: str | None = None

    # --- persistence ----------------------------------------------------------

    async def save(
        self,
        redis: aredis.Redis[bytes] | None = None,
    ) -> None:
        """Persist checkpoint to Redis (TTL=7d) or local JSON fallback.

        Spec: specs/ai/long-running-session.md §3, §6
        """
        self.updated_at = _now_iso()
        payload = _serialize(self)

        if redis is not None:
            key = _REDIS_KEY_PREFIX + self.session_id
            await redis.set(key, json.dumps(payload), ex=_REDIS_TTL_SECONDS)
            logger.info(
                "checkpoint_saved",
                session_id=self.session_id,
                current_step=self.current_step,
                completed=len(self.completed_steps),
                backend="redis",
            )
        else:
            _save_local(self.session_id, payload)
            logger.info(
                "checkpoint_saved",
                session_id=self.session_id,
                current_step=self.current_step,
                backend="local",
            )

    async def mark_step_complete(
        self,
        sprint_id: str,
        redis: aredis.Redis[bytes] | None = None,
    ) -> None:
        """Mark a sprint as complete and advance current_step.

        Spec: specs/ai/long-running-session.md §6
        """
        if sprint_id not in self.completed_steps:
            self.completed_steps.append(sprint_id)
        self.current_step = len(self.completed_steps)
        await self.save(redis=redis)

    async def delete(self, redis: aredis.Redis[bytes] | None = None) -> None:
        """Remove checkpoint on successful completion.

        Spec: specs/ai/long-running-session.md §6
        """
        if redis is not None:
            await redis.delete(_REDIS_KEY_PREFIX + self.session_id)
        else:
            path = _local_path(self.session_id)
            if path.exists():
                path.unlink()
        logger.info("checkpoint_deleted", session_id=self.session_id)

    # --- factory --------------------------------------------------------------

    @classmethod
    async def resume(
        cls,
        session_id: str,
        redis: aredis.Redis[bytes] | None = None,
    ) -> SessionCheckpoint | None:
        """Load an existing checkpoint, or return None if not found.

        Spec: specs/ai/long-running-session.md §4
        Raises ValueError if the stored payload is corrupted (plan-corrupted failure).
        """
        raw: str | None = None

        if redis is not None:
            raw_bytes = await redis.get(_REDIS_KEY_PREFIX + session_id)
            raw = raw_bytes.decode() if raw_bytes else None
        else:
            path = _local_path(session_id)
            if path.exists():
                raw = path.read_text()

        if raw is None:
            return None

        try:
            payload = json.loads(raw)
            checkpoint = _deserialize(payload)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # plan-corrupted — caller must emit [HITL-ESCALATE], never silently recover
            raise ValueError(f"Checkpoint for session {session_id} is corrupted: {exc}") from exc

        logger.info(
            "checkpoint_resumed",
            session_id=session_id,
            current_step=checkpoint.current_step,
            completed=len(checkpoint.completed_steps),
        )
        return checkpoint

    @classmethod
    def new(
        cls,
        task_id: str,
        sprint_plan: ProductSpec,
        correlation_id: str | None = None,
    ) -> SessionCheckpoint:
        """Create a fresh checkpoint for a new sprint plan."""
        return cls(
            session_id=str(uuid.uuid4()),
            task_id=task_id,
            sprint_plan=sprint_plan,
            correlation_id=correlation_id,
        )


# --- helpers ------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _local_path(session_id: str) -> Path:
    return _LOCAL_CHECKPOINT_DIR / f"{session_id}.json"


def _save_local(session_id: str, payload: dict[str, Any]) -> None:
    _LOCAL_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    _local_path(session_id).write_text(json.dumps(payload, indent=2))


def _serialize(cp: SessionCheckpoint) -> dict[str, Any]:

    plan = cp.sprint_plan
    return {
        "session_id": cp.session_id,
        "task_id": cp.task_id,
        "sprint_plan": {
            "task_id": plan.task_id,
            "detailed_description": plan.detailed_description,
            "sprint_contracts": [
                {
                    "sprint_id": sc.sprint_id,
                    "objectives": sc.objectives,
                    "success_criteria": sc.success_criteria,
                    "correlation_id": sc.correlation_id,
                }
                for sc in plan.sprint_contracts
            ],
            "ai_feature_opportunities": plan.ai_feature_opportunities,
        },
        "current_step": cp.current_step,
        "completed_steps": cp.completed_steps,
        "created_at": cp.created_at,
        "updated_at": cp.updated_at,
        "correlation_id": cp.correlation_id,
    }


def _deserialize(payload: dict[str, Any]) -> SessionCheckpoint:
    from src.agents.harness.models import ProductSpec, SprintContract

    plan_data = payload["sprint_plan"]
    sprint_plan = ProductSpec(
        task_id=plan_data["task_id"],
        detailed_description=plan_data["detailed_description"],
        sprint_contracts=[
            SprintContract(
                sprint_id=sc["sprint_id"],
                objectives=sc["objectives"],
                success_criteria=sc["success_criteria"],
                correlation_id=sc.get("correlation_id"),
            )
            for sc in plan_data["sprint_contracts"]
        ],
        ai_feature_opportunities=plan_data.get("ai_feature_opportunities", []),
    )
    return SessionCheckpoint(
        session_id=payload["session_id"],
        task_id=payload["task_id"],
        sprint_plan=sprint_plan,
        current_step=payload["current_step"],
        completed_steps=payload["completed_steps"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        correlation_id=payload.get("correlation_id"),
    )
