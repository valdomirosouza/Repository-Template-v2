"""Agent action rate limits and scope restrictions.

check_rate_limit() and check_scope_limit() are mandatory guardrails called
before every agent action. Both must pass before execution proceeds.

Spec: specs/ai/guardrails.md (Layer 3 — Action Limits)
ADR:  ADR-0010 (Agent Framework Selection)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from src.observability.logger import get_logger
from src.shared.config import settings

logger = get_logger("action_limits")


@dataclass
class ActionLimitConfig:
    agent_id: str
    max_actions_per_minute: int = 10
    max_actions_per_hour: int = 100
    max_actions_per_day: int = 500
    allowed_action_types: list[str] = field(default_factory=list)
    max_records_affected: int = 50
    allowed_environments: list[str] = field(default_factory=lambda: ["staging", "production"])


class ActionLimiter:
    """Enforces per-agent rate limits and scope restrictions using Redis sliding windows."""

    def __init__(self, config: ActionLimitConfig, redis_client: object) -> None:
        self._config = config
        self._redis = redis_client

    async def check_rate_limit(self, agent_id: str, action_type: str) -> bool:
        """Return True if the action is within rate limits.

        Uses a Redis sliding window counter per time bucket.
        Returns False (and logs the denial) when any limit is exceeded.
        """
        now = int(time.time())
        minute_key = f"limits:{agent_id}:minute:{now // 60}"
        hour_key = f"limits:{agent_id}:hour:{now // 3600}"
        day_key = f"limits:{agent_id}:day:{now // 86400}"

        try:
            pipe = self._redis.pipeline()  # type: ignore[attr-defined]
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)
            pipe.incr(hour_key)
            pipe.expire(hour_key, 7200)
            pipe.incr(day_key)
            pipe.expire(day_key, 172800)
            results = await asyncio.wait_for(
                pipe.execute(),
                timeout=settings.redis_call_timeout_seconds,
            )

            minute_count, _, hour_count, _, day_count, _ = results

            if minute_count > self._config.max_actions_per_minute:
                logger.warning(
                    "Rate limit exceeded: per-minute",
                    agent_id=agent_id,
                    action_type=action_type,
                    count=minute_count,
                    limit=self._config.max_actions_per_minute,
                )
                return False

            if hour_count > self._config.max_actions_per_hour:
                logger.warning(
                    "Rate limit exceeded: per-hour",
                    agent_id=agent_id,
                    action_type=action_type,
                    count=hour_count,
                    limit=self._config.max_actions_per_hour,
                )
                return False

            if day_count > self._config.max_actions_per_day:
                logger.warning(
                    "Rate limit exceeded: per-day",
                    agent_id=agent_id,
                    action_type=action_type,
                    count=day_count,
                    limit=self._config.max_actions_per_day,
                )
                return False

        except Exception as exc:
            # Redis failure → deny action (fail closed, never fail open)
            logger.error(
                "Rate limit check failed — denying action",
                agent_id=agent_id,
                action_type=action_type,
                error=str(exc),
            )
            return False

        return True

    def check_scope_limit(
        self,
        agent_id: str,
        action_type: str,
        parameters: dict[str, Any],
    ) -> tuple[bool, str]:
        """Return (allowed, reason). Validates action type and affected record count."""

        if (
            self._config.allowed_action_types
            and action_type not in self._config.allowed_action_types
        ):
            reason = f"action_type '{action_type}' not in allowed list for agent '{agent_id}'"
            logger.warning("Scope limit: action type denied", agent_id=agent_id, reason=reason)
            return False, reason

        affected = parameters.get("record_count") or parameters.get("affected_count") or 1
        if isinstance(affected, int) and affected > self._config.max_records_affected:
            reason = (
                f"affected records {affected} exceeds limit "
                f"{self._config.max_records_affected} for agent '{agent_id}'"
            )
            logger.warning("Scope limit: record count denied", agent_id=agent_id, reason=reason)
            return False, reason

        return True, "ok"

    async def check(self, action_type: str, parameters: dict[str, Any]) -> None:
        """Unified guardrail: scope limit then rate limit. Raises ValueError on denial.

        Called by AgentOrchestrator before every action execution.
        Uses self._config.agent_id as the rate-limit key.
        """
        allowed, reason = self.check_scope_limit(self._config.agent_id, action_type, parameters)
        if not allowed:
            raise ValueError(f"Action denied by scope limit: {reason}")

        within_limits = await self.check_rate_limit(self._config.agent_id, action_type)
        if not within_limits:
            raise ValueError(f"Action denied by rate limit for agent '{self._config.agent_id}'")

    async def record_action(self, agent_id: str, action_type: str) -> None:
        """Increment Redis counters after a successful action execution."""
        now = int(time.time())
        try:
            pipe = self._redis.pipeline()  # type: ignore[attr-defined]
            for key, ttl in [
                (f"limits:{agent_id}:minute:{now // 60}", 120),
                (f"limits:{agent_id}:hour:{now // 3600}", 7200),
                (f"limits:{agent_id}:day:{now // 86400}", 172800),
            ]:
                pipe.incr(key)
                pipe.expire(key, ttl)
            await asyncio.wait_for(
                pipe.execute(),
                timeout=settings.redis_call_timeout_seconds,
            )
        except Exception as exc:
            logger.error(
                "Failed to record action in rate limiter",
                agent_id=agent_id,
                action_type=action_type,
                error=str(exc),
            )
