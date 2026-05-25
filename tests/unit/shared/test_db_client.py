"""Unit tests for src/shared/db_client.py — ResilientDBPool.

Spec: specs/system/architecture.md (Resilience)
ADR:  ADR-0002 (Technology Stack Selection)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.shared.db_client import ResilientDBPool
from src.shared.retry import CircuitBreaker, CircuitBreakerError, TransientError

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_pool(return_value: object = "ok") -> MagicMock:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value=return_value)
    pool.fetchval = AsyncMock(return_value=return_value)
    pool.fetch = AsyncMock(return_value=[return_value])
    pool.close = AsyncMock()
    return pool


# ── Happy path ────────────────────────────────────────────────────────────────


class TestResilientDBPoolHappyPath:
    @pytest.mark.asyncio
    async def test_execute_delegates_to_pool(self):
        pool = _make_pool("INSERT 1")
        wrapped = ResilientDBPool(pool)
        result = await wrapped.execute("INSERT INTO t VALUES ($1)", 42)
        pool.execute.assert_called_once_with("INSERT INTO t VALUES ($1)", 42)
        assert result == "INSERT 1"

    @pytest.mark.asyncio
    async def test_fetchval_delegates_to_pool(self):
        pool = _make_pool(99)
        wrapped = ResilientDBPool(pool)
        result = await wrapped.fetchval("SELECT 1")
        assert result == 99

    @pytest.mark.asyncio
    async def test_fetch_delegates_to_pool(self):
        pool = _make_pool("row")
        wrapped = ResilientDBPool(pool)
        rows = await wrapped.fetch("SELECT * FROM t")
        assert rows == ["row"]

    @pytest.mark.asyncio
    async def test_close_delegates_to_pool(self):
        pool = _make_pool()
        wrapped = ResilientDBPool(pool)
        await wrapped.close()
        pool.close.assert_called_once()

    def test_acquire_returns_pool_context_manager(self):
        pool = _make_pool()
        pool.acquire = MagicMock(return_value="ctx")
        wrapped = ResilientDBPool(pool)
        assert wrapped.acquire() == "ctx"


# ── Circuit breaker ───────────────────────────────────────────────────────────


class TestResilientDBPoolCircuitBreaker:
    @pytest.mark.asyncio
    async def test_open_circuit_raises_circuit_breaker_error(self):
        pool = _make_pool()
        cb = CircuitBreaker(threshold=1, reset_seconds=3600)
        cb.record_failure()  # open the circuit
        wrapped = ResilientDBPool(pool, circuit_breaker=cb)

        with pytest.raises(CircuitBreakerError):
            await wrapped.execute("SELECT 1")

        pool.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        pool = _make_pool("ok")
        cb = CircuitBreaker(threshold=5)
        cb.record_failure()
        cb.record_failure()
        wrapped = ResilientDBPool(pool, circuit_breaker=cb)

        await wrapped.execute("SELECT 1")
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_transient_error_increments_circuit_breaker(self):
        pool = MagicMock()
        pool.execute = AsyncMock(side_effect=Exception("connection reset by peer"))
        cb = CircuitBreaker(threshold=10)
        wrapped = ResilientDBPool(pool, circuit_breaker=cb, timeout=5.0)

        with pytest.raises(TransientError):
            await wrapped.execute("SELECT 1")

        assert cb._failure_count > 0


# ── Timeout ───────────────────────────────────────────────────────────────────


class TestResilientDBPoolTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_transient_error(self):
        pool = MagicMock()

        async def slow(*args, **kwargs):
            await asyncio.sleep(10)

        pool.execute = slow
        wrapped = ResilientDBPool(pool, timeout=0.01)

        with pytest.raises(TransientError, match="timed out"):
            await wrapped.execute("SELECT 1")
