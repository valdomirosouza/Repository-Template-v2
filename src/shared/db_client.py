"""Resilient wrapper for asyncpg pool operations.

Spec: specs/system/architecture.md (Resilience)
ADR:  ADR-0002 (Technology Stack Selection)

Applies the same timeout + exponential-backoff + circuit-breaker pattern used by
ResilientLLMClientWrapper (retry.py) to all asyncpg pool operations.

Usage::

    raw_pool = await asyncpg.create_pool(settings.database_url, ...)
    pool = ResilientDBPool(raw_pool)

    await pool.execute("INSERT INTO ...")
    row = await pool.fetchval("SELECT 1")
    rows = await pool.fetch("SELECT * FROM ...")

    # Acquire a raw connection for multi-statement transactions:
    async with pool.acquire() as conn:
        await conn.execute(...)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from src.observability.logger import get_logger
from src.observability.metrics import DB_POOL_CONNECTIONS_ACQUIRED, DB_POOL_CONNECTIONS_AVAILABLE
from src.shared.retry import CircuitBreaker, CircuitBreakerError, TransientError, with_retry

if TYPE_CHECKING:
    import asyncpg

logger = get_logger("db_client")

_TRANSIENT_KEYWORDS = ("connection", "timeout", "unavailable", "too many", "reset by peer")

_DEFAULT_TIMEOUT = 5.0


class ResilientDBPool:
    """Wraps asyncpg.Pool with per-call timeout, exponential-backoff retry, and circuit breaker.

    The circuit breaker shares the same thresholds as the LLM client
    (llm_circuit_breaker_threshold / llm_circuit_breaker_reset_seconds) via the default
    CircuitBreaker constructor. Pass a custom instance to tune independently.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        timeout: float = _DEFAULT_TIMEOUT,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._pool = pool
        self._timeout = timeout
        self._cb = circuit_breaker or CircuitBreaker(name="db")

    # ── Public interface ──────────────────────────────────────────────────────

    async def execute(self, query: str, *args: Any) -> str:
        result: str = await self._call(self._pool.execute, query, *args)
        return result

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._call(self._pool.fetchval, query, *args)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        result: list[Any] = await self._call(self._pool.fetch, query, *args)
        return result

    def acquire(self) -> Any:
        """Return the pool's acquire() context manager for multi-statement transactions.

        The caller is responsible for handling timeouts and retries on the acquired
        connection; this method intentionally bypasses the circuit breaker so that
        explicit transaction control is preserved.
        """
        return self._pool.acquire()

    async def close(self) -> None:
        """Gracefully close the underlying pool."""
        await self._pool.close()

    def _emit_pool_metrics(self) -> None:
        """Update pool saturation gauges after each successful operation."""
        try:
            total = self._pool.get_size()
            idle = self._pool.get_idle_size()
            DB_POOL_CONNECTIONS_ACQUIRED.set(total - idle)
            DB_POOL_CONNECTIONS_AVAILABLE.set(idle)
        except Exception:  # noqa: S110 — metric emission must never raise
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    @with_retry()
    async def _call(self, method: Any, *args: Any) -> Any:
        if self._cb.is_open:
            logger.warning("DB circuit breaker OPEN — fast-failing call")
            raise CircuitBreakerError("DB circuit breaker is open — upstream is unavailable")

        try:
            result = await asyncio.wait_for(method(*args), timeout=self._timeout)
            self._cb.record_success()
            self._emit_pool_metrics()
            return result
        except TimeoutError as exc:
            self._cb.record_failure()
            raise TransientError(f"DB call timed out after {self._timeout}s: {exc}") from exc
        except Exception as exc:
            error_str = str(exc).lower()
            if any(kw in error_str for kw in _TRANSIENT_KEYWORDS):
                self._cb.record_failure()
                raise TransientError(f"Transient DB error: {exc}") from exc
            raise
