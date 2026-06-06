"""Unit tests for SessionCheckpoint — save/resume/delete lifecycle.

Spec: specs/ai/long-running-session.md
ADR:  ADR-0033 (Long-Running Agent Session Durability)
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.harness.models import ProductSpec, SprintContract
from src.agents.harness.session_checkpoint import (
    _REDIS_KEY_PREFIX,
    _REDIS_TTL_SECONDS,
    SessionCheckpoint,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_plan(num_sprints: int = 2) -> ProductSpec:
    return ProductSpec(
        task_id=str(uuid.uuid4()),
        detailed_description="Test plan",
        sprint_contracts=[
            SprintContract(
                sprint_id=str(uuid.uuid4()),
                objectives=[f"objective {i}"],
                success_criteria=[f"criterion {i}"],
            )
            for i in range(num_sprints)
        ],
    )


def _make_checkpoint(plan: ProductSpec | None = None) -> SessionCheckpoint:
    plan = plan or _make_plan()
    return SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan)


def _make_redis(stored: dict | None = None) -> MagicMock:
    redis = MagicMock()
    raw = json.dumps(stored).encode() if stored else None
    redis.get = AsyncMock(return_value=raw)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


# ── new() ─────────────────────────────────────────────────────────────────────


class TestNew:
    def test_generates_session_id(self):
        cp = _make_checkpoint()
        assert cp.session_id
        uuid.UUID(cp.session_id)  # valid UUID

    def test_starts_at_step_zero(self):
        cp = _make_checkpoint()
        assert cp.current_step == 0
        assert cp.completed_steps == []

    def test_stores_plan(self):
        plan = _make_plan(num_sprints=3)
        cp = SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan)
        assert len(cp.sprint_plan.sprint_contracts) == 3

    def test_accepts_correlation_id(self):
        plan = _make_plan()
        cp = SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan, correlation_id="corr-1")
        assert cp.correlation_id == "corr-1"


# ── save() via Redis ──────────────────────────────────────────────────────────


class TestSaveRedis:
    @pytest.mark.asyncio
    async def test_sets_key_with_ttl(self):
        cp = _make_checkpoint()
        redis = _make_redis()

        await cp.save(redis=redis)

        redis.set.assert_awaited_once()
        call_args = redis.set.call_args
        assert call_args.args[0] == _REDIS_KEY_PREFIX + cp.session_id
        assert call_args.kwargs["ex"] == _REDIS_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_payload_is_valid_json(self):
        cp = _make_checkpoint()
        redis = _make_redis()

        await cp.save(redis=redis)

        raw = redis.set.call_args.args[1]
        parsed = json.loads(raw)
        assert parsed["session_id"] == cp.session_id
        assert "sprint_plan" in parsed

    @pytest.mark.asyncio
    async def test_updated_at_refreshed_on_save(self):
        cp = _make_checkpoint()
        original_ts = cp.updated_at

        import asyncio

        await asyncio.sleep(0.01)
        await cp.save(redis=_make_redis())

        assert cp.updated_at >= original_ts


# ── save() local fallback ─────────────────────────────────────────────────────


class TestSaveLocal:
    @pytest.mark.asyncio
    async def test_writes_json_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agents.harness.session_checkpoint._LOCAL_CHECKPOINT_DIR", tmp_path)
        cp = _make_checkpoint()

        await cp.save(redis=None)

        written = tmp_path / f"{cp.session_id}.json"
        assert written.exists()
        data = json.loads(written.read_text())
        assert data["session_id"] == cp.session_id

    @pytest.mark.asyncio
    async def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        target = tmp_path / "nested" / "checkpoints"
        monkeypatch.setattr("src.agents.harness.session_checkpoint._LOCAL_CHECKPOINT_DIR", target)
        cp = _make_checkpoint()

        await cp.save(redis=None)

        assert (target / f"{cp.session_id}.json").exists()


# ── resume() ─────────────────────────────────────────────────────────────────


class TestResume:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        redis = _make_redis(stored=None)
        result = await SessionCheckpoint.resume("nonexistent", redis=redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_round_trips_through_redis(self):
        plan = _make_plan(num_sprints=2)
        cp = SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan, correlation_id="c-99")
        cp.current_step = 1
        cp.completed_steps = [plan.sprint_contracts[0].sprint_id]

        from src.agents.harness.session_checkpoint import _serialize

        payload = _serialize(cp)
        redis = _make_redis(stored=payload)

        loaded = await SessionCheckpoint.resume(cp.session_id, redis=redis)

        assert loaded is not None
        assert loaded.session_id == cp.session_id
        assert loaded.current_step == 1
        assert len(loaded.completed_steps) == 1
        assert loaded.correlation_id == "c-99"

    @pytest.mark.asyncio
    async def test_raises_on_corrupted_payload(self):
        redis = MagicMock()
        redis.get = AsyncMock(return_value=b"not-valid-json{{{")

        with pytest.raises(ValueError, match="corrupted"):
            await SessionCheckpoint.resume("bad-session", redis=redis)

    @pytest.mark.asyncio
    async def test_raises_on_missing_required_field(self):
        redis = _make_redis(stored={"session_id": "x"})  # missing sprint_plan etc.

        with pytest.raises(ValueError, match="corrupted"):
            await SessionCheckpoint.resume("x", redis=redis)

    @pytest.mark.asyncio
    async def test_local_fallback_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agents.harness.session_checkpoint._LOCAL_CHECKPOINT_DIR", tmp_path)
        plan = _make_plan()
        cp = SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan)
        await cp.save(redis=None)

        loaded = await SessionCheckpoint.resume(cp.session_id, redis=None)

        assert loaded is not None
        assert loaded.session_id == cp.session_id


# ── mark_step_complete() ──────────────────────────────────────────────────────


class TestMarkStepComplete:
    @pytest.mark.asyncio
    async def test_appends_sprint_id_and_advances_step(self):
        plan = _make_plan(num_sprints=3)
        cp = SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan)
        sprint_id = plan.sprint_contracts[0].sprint_id

        await cp.mark_step_complete(sprint_id, redis=_make_redis())

        assert sprint_id in cp.completed_steps
        assert cp.current_step == 1

    @pytest.mark.asyncio
    async def test_idempotent_on_duplicate(self):
        plan = _make_plan()
        cp = SessionCheckpoint.new(task_id=plan.task_id, sprint_plan=plan)
        sprint_id = plan.sprint_contracts[0].sprint_id

        await cp.mark_step_complete(sprint_id, redis=_make_redis())
        await cp.mark_step_complete(sprint_id, redis=_make_redis())

        assert cp.completed_steps.count(sprint_id) == 1
        assert cp.current_step == 1


# ── delete() ─────────────────────────────────────────────────────────────────


class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_redis_key(self):
        cp = _make_checkpoint()
        redis = _make_redis()

        await cp.delete(redis=redis)

        redis.delete.assert_awaited_once_with(_REDIS_KEY_PREFIX + cp.session_id)

    @pytest.mark.asyncio
    async def test_deletes_local_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agents.harness.session_checkpoint._LOCAL_CHECKPOINT_DIR", tmp_path)
        cp = _make_checkpoint()
        await cp.save(redis=None)
        assert (tmp_path / f"{cp.session_id}.json").exists()

        await cp.delete(redis=None)

        assert not (tmp_path / f"{cp.session_id}.json").exists()

    @pytest.mark.asyncio
    async def test_delete_local_no_error_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agents.harness.session_checkpoint._LOCAL_CHECKPOINT_DIR", tmp_path)
        cp = _make_checkpoint()
        await cp.delete(redis=None)  # file never created — must not raise
