"""Retry decorator and circuit breaker for transient external-call failures.

Spec: specs/ai/agent-design.md (Resilience)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)

Usage::

    from src.shared.retry import with_retry, TransientError

    @with_retry(max_attempts=3)
    async def call_external_api() -> str:
        ...   # raise TransientError on recoverable failures

Circuit breaker usage::

    from src.shared.retry import ResilientLLMClientWrapper

    client = ResilientLLMClientWrapper(raw_llm_client)
    # Applies timeout + exponential backoff + circuit breaker automatically.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from src.observability.logger import get_logger
from src.observability.metrics import CIRCUIT_BREAKER_STATE
from src.shared.config import settings
from src.shared.llm_client import LLMClient, TimeoutLLMClientWrapper

logger = get_logger("retry")

F = TypeVar("F")


class TransientError(Exception):
    """Raise this to signal a recoverable failure that should trigger a retry."""


class CircuitBreakerError(Exception):
    """Raised when the circuit is OPEN and fast-failing all calls."""


def with_retry(
    max_attempts: int | None = None,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
) -> Callable[[Any], Any]:
    """Async retry decorator: exponential backoff + jitter on TransientError.

    Args:
        max_attempts: Max total attempts (default: settings.llm_retry_max_attempts).
        min_wait:     Minimum wait between retries in seconds.
        max_wait:     Maximum wait between retries in seconds.
    """
    attempts = max_attempts or settings.llm_retry_max_attempts

    def decorator(func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(min=min_wait, max=max_wait) + wait_random(0, 2),
                retry=retry_if_exception_type(TransientError),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)
            raise RetryError(None)  # type: ignore[arg-type]  # unreachable

        return wrapper

    return decorator


class CircuitBreaker:
    """Simple three-state circuit breaker (CLOSED → OPEN → HALF_OPEN).

    States:
      CLOSED:    Normal operation. Failures increment _failure_count.
      OPEN:      Fast-fail all calls. Entered after _threshold consecutive failures.
      HALF_OPEN: One probe call allowed. Success → CLOSED; failure → OPEN.

    The `name` parameter labels the `circuit_breaker_state` Prometheus Gauge
    so each client (e.g. "llm", "db") is tracked independently (REM-014).
    """

    def __init__(
        self,
        name: str = "unknown",
        threshold: int | None = None,
        reset_seconds: float | None = None,
    ) -> None:
        self._name = name
        self._threshold = threshold or settings.llm_circuit_breaker_threshold
        self._reset = reset_seconds or settings.llm_circuit_breaker_reset_seconds
        self._failure_count = 0
        self._opened_at: float | None = None
        self._half_open = False
        CIRCUIT_BREAKER_STATE.labels(self._name).set(0.0)  # starts CLOSED

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self._reset:
            self._enter_half_open()
            return False
        return True

    def _enter_half_open(self) -> None:
        self._half_open = True
        CIRCUIT_BREAKER_STATE.labels(self._name).set(0.5)

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_at = None
        self._half_open = False
        CIRCUIT_BREAKER_STATE.labels(self._name).set(0.0)

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._threshold or self._half_open:
            self._opened_at = time.monotonic()
            self._half_open = False
            CIRCUIT_BREAKER_STATE.labels(self._name).set(1.0)
            logger.warning(
                "Circuit breaker OPENED",
                client=self._name,
                threshold=self._threshold,
                failure_count=self._failure_count,
            )


class ResilientLLMClientWrapper:
    """Wraps an LLMClient with timeout + exponential backoff + circuit breaker.

    Compose this over any LLMClient in production:
        client = ResilientLLMClientWrapper(AnthropicLLMClient(...))

    The circuit breaker opens after llm_circuit_breaker_threshold consecutive
    failures and probes again after llm_circuit_breaker_reset_seconds.
    """

    def __init__(
        self,
        client: LLMClient,
        timeout_seconds: float | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._inner = TimeoutLLMClientWrapper(
            client,
            timeout_seconds=timeout_seconds or settings.llm_call_timeout_seconds,
        )
        self._cb = circuit_breaker or CircuitBreaker(name="llm")

    async def complete(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> str:
        if self._cb.is_open:
            logger.warning("Circuit breaker OPEN — fast-failing LLM call", trace_id=trace_id)
            raise CircuitBreakerError("LLM circuit breaker is open — upstream is unavailable")

        try:
            result: str = await self._call_with_retry(user=user, system=system, trace_id=trace_id)
            self._cb.record_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception:
            self._cb.record_failure()
            raise

    @with_retry()
    async def _call_with_retry(
        self,
        user: str,
        system: str,
        trace_id: str | None,
    ) -> str:
        try:
            return await self._inner.complete(user=user, system=system, trace_id=trace_id)
        except TimeoutError as exc:
            raise TransientError(f"LLM call timed out: {exc}") from exc
        except Exception as exc:
            # Re-raise as TransientError only for errors that are worth retrying.
            # Connection errors, rate limits, server errors (5xx) → transient.
            # Authentication errors, validation errors → not transient (re-raise as-is).
            error_str = str(exc).lower()
            transient = ("timeout", "connect", "rate", "503", "502", "500")
            if any(keyword in error_str for keyword in transient):
                raise TransientError(f"Transient LLM error: {exc}") from exc
            raise
