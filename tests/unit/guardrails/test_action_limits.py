"""Unit tests for ActionLimiter scope and rate limit guardrails.

Spec: specs/ai/guardrails.md (Layer 3 — Action Limits)
ADR:  ADR-0010 (Agent Framework Selection)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.guardrails.action_limits import ActionLimitConfig, ActionLimiter

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_limiter(
    allowed_action_types: list[str] | None = None,
    max_records_affected: int = 50,
    max_actions_per_minute: int = 10,
) -> ActionLimiter:
    config = ActionLimitConfig(
        agent_id="agent-test",
        allowed_action_types=allowed_action_types or [],
        max_records_affected=max_records_affected,
        max_actions_per_minute=max_actions_per_minute,
    )
    redis = MagicMock()
    return ActionLimiter(config=config, redis_client=redis)


def _make_limiter_with_mock_redis(
    pipe_results: list[int] | None = None,
    allowed_action_types: list[str] | None = None,
    max_actions_per_minute: int = 10,
) -> ActionLimiter:
    """Return a limiter whose Redis pipeline returns controlled counter values."""
    if pipe_results is None:
        pipe_results = [1, True, 1, True, 1, True]  # well below all limits

    config = ActionLimitConfig(
        agent_id="agent-test",
        allowed_action_types=allowed_action_types or [],
        max_actions_per_minute=max_actions_per_minute,
        max_actions_per_hour=100,
        max_actions_per_day=500,
    )

    pipe = AsyncMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=pipe_results)

    redis = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe)

    return ActionLimiter(config=config, redis_client=redis)


# ── check_scope_limit ─────────────────────────────────────────────────────────


class TestCheckScopeLimit:
    def test_denies_disallowed_action_type(self):
        limiter = _make_limiter(allowed_action_types=["read", "list"])
        allowed, reason = limiter.check_scope_limit("agent-test", "delete", {})
        assert not allowed
        assert "delete" in reason

    def test_allows_permitted_action_type(self):
        limiter = _make_limiter(allowed_action_types=["read", "list"])
        allowed, reason = limiter.check_scope_limit("agent-test", "read", {})
        assert allowed
        assert reason == "ok"

    def test_denies_excess_record_count(self):
        limiter = _make_limiter(max_records_affected=10)
        allowed, reason = limiter.check_scope_limit("agent-test", "write", {"record_count": 11})
        assert not allowed
        assert "11" in reason

    def test_allows_within_record_count(self):
        limiter = _make_limiter(max_records_affected=50)
        allowed, _ = limiter.check_scope_limit("agent-test", "write", {"record_count": 50})
        assert allowed

    def test_passes_when_no_allowed_types_configured(self):
        limiter = _make_limiter(allowed_action_types=[])
        allowed, _ = limiter.check_scope_limit("agent-test", "anything", {})
        assert allowed


# ── check (unified guardrail) ─────────────────────────────────────────────────


class TestUnifiedCheck:
    @pytest.mark.asyncio
    async def test_raises_on_scope_denial(self):
        limiter = _make_limiter(allowed_action_types=["read"])
        with pytest.raises(ValueError, match="scope limit"):
            await limiter.check("write", {})

    @pytest.mark.asyncio
    async def test_raises_on_rate_limit_denial(self):
        # minute count above max_actions_per_minute → rate limit denial
        limiter = _make_limiter_with_mock_redis(
            pipe_results=[11, True, 1, True, 1, True],  # minute count = 11 > 10
            max_actions_per_minute=10,
        )
        with pytest.raises(ValueError, match="rate limit"):
            await limiter.check("read", {})

    @pytest.mark.asyncio
    async def test_passes_when_within_all_limits(self):
        limiter = _make_limiter_with_mock_redis(
            pipe_results=[1, True, 1, True, 1, True],
        )
        # should not raise
        await limiter.check("read", {})
