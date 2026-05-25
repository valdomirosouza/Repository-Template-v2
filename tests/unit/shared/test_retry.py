"""Unit tests for ResilientLLMClientWrapper in src/shared/retry.py.

CircuitBreaker and with_retry are also exercised here. CircuitBreaker
state transitions are covered more exhaustively in test_db_client.py
(it shares the same class); these tests focus on the LLM wrapper paths.

Spec: specs/ai/agent-design.md (Resilience)
ADR:  ADR-0014 (Multi-Agent Harness Strategy)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.shared.retry import (
    CircuitBreaker,
    CircuitBreakerError,
    ResilientLLMClientWrapper,
)


def _make_client(return_value: str = "response") -> AsyncMock:
    client = AsyncMock()
    client.complete.return_value = return_value
    return client


def _open_circuit(threshold: int = 1) -> CircuitBreaker:
    cb = CircuitBreaker(threshold=threshold)
    for _ in range(threshold):
        cb.record_failure()
    return cb


class TestResilientLLMClientWrapperSuccess:
    @pytest.mark.asyncio
    async def test_returns_llm_response(self) -> None:
        wrapper = ResilientLLMClientWrapper(_make_client("hello"))
        result = await wrapper.complete(user="ping")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_records_success_in_circuit_breaker(self) -> None:
        cb = CircuitBreaker(threshold=5)
        cb.record_failure()
        wrapper = ResilientLLMClientWrapper(_make_client(), circuit_breaker=cb)
        await wrapper.complete(user="ping")
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_passes_trace_id_to_inner_client(self) -> None:
        client = _make_client()
        wrapper = ResilientLLMClientWrapper(client)
        await wrapper.complete(user="q", system="sys", trace_id="t-123")
        client.complete.assert_awaited_once()
        _, kwargs = client.complete.call_args
        assert kwargs.get("trace_id") == "t-123"


class TestResilientLLMClientWrapperCircuitBreaker:
    @pytest.mark.asyncio
    async def test_raises_circuit_breaker_error_when_open(self) -> None:
        cb = _open_circuit(threshold=1)
        wrapper = ResilientLLMClientWrapper(_make_client(), circuit_breaker=cb)
        with pytest.raises(CircuitBreakerError):
            await wrapper.complete(user="ping")

    @pytest.mark.asyncio
    async def test_does_not_call_llm_when_circuit_open(self) -> None:
        client = _make_client()
        wrapper = ResilientLLMClientWrapper(client, circuit_breaker=_open_circuit())
        with pytest.raises(CircuitBreakerError):
            await wrapper.complete(user="ping")
        client.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_records_failure_on_non_transient_error(self) -> None:
        cb = CircuitBreaker(threshold=10)
        client = _make_client()
        client.complete.side_effect = ValueError("invalid credentials — not transient")
        wrapper = ResilientLLMClientWrapper(client, circuit_breaker=cb)
        with pytest.raises(ValueError):
            await wrapper.complete(user="ping")
        assert cb._failure_count == 1


class TestResilientLLMClientWrapperErrorWrapping:
    @pytest.mark.asyncio
    async def test_non_transient_exception_propagates_unchanged(self) -> None:
        client = _make_client()
        client.complete.side_effect = ValueError("malformed request")
        wrapper = ResilientLLMClientWrapper(client, circuit_breaker=CircuitBreaker(threshold=5))
        with pytest.raises(ValueError, match="malformed request"):
            await wrapper.complete(user="ping")

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_repeated_non_transient_failures(self) -> None:
        cb = CircuitBreaker(threshold=2)
        client = _make_client()
        client.complete.side_effect = ValueError("permission denied — not retryable")
        wrapper = ResilientLLMClientWrapper(client, circuit_breaker=cb)
        for _ in range(2):
            with pytest.raises(ValueError):
                await wrapper.complete(user="ping")
        assert cb.is_open is True
