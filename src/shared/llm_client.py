"""LLMClient protocol — abstraction over LLM providers.

Spec: specs/ai/agent-design.md (Reason phase)
ADR:  ADR-0010 (Agent Framework Selection), ADR-0002 (Technology Stack Selection)

All LLM calls in this system must go through an implementation of this protocol.
The protocol is typed structurally — any object with a compatible `complete()`
method satisfies it without explicit registration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """Structured response from an LLM provider call."""

    content: str
    action: str | None = None
    parameters: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


@runtime_checkable
class LLMClient(Protocol):
    """Structural protocol for LLM providers.

    Implementations: AnthropicClient, StubLLMClient (tests), etc.
    The caller always passes masked context — never raw PII.
    """

    async def complete(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> str:
        """Send a completion request and return the response content as a string."""
        ...


class TimeoutLLMClientWrapper:
    """Wraps any LLMClient and enforces a per-call asyncio timeout.

    Raises asyncio.TimeoutError if the underlying call exceeds timeout_seconds.
    Inject this wrapper wherever a production LLMClient is used.
    """

    def __init__(self, client: LLMClient, timeout_seconds: float = 30.0) -> None:
        self._client = client
        self._timeout = timeout_seconds

    async def complete(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> str:
        return await asyncio.wait_for(
            self._client.complete(user=user, system=system, trace_id=trace_id),
            timeout=self._timeout,
        )


@dataclass
class LLMCallMetadata:
    """Token usage and finish metadata from an LLM call — used by OTel wrapper."""

    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    model: str = ""


class AnthropicLLMClient:
    """Thin wrapper around the Anthropic SDK for production use.

    Uses settings.llm_api_key and settings.llm_model.
    Always wrap with TimeoutLLMClientWrapper in callers.
    """

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        from src.shared.config import settings

        self._client = AsyncAnthropic(api_key=settings.llm_api_key)
        self._model = settings.llm_model

    async def complete(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> str:
        text, _ = await self.complete_with_metadata(user=user, system=system, trace_id=trace_id)
        return text

    async def complete_with_metadata(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> tuple[str, LLMCallMetadata]:
        """Call the Anthropic API and return the response text plus token metadata."""
        from anthropic.types import TextBlock

        from src.shared.config import settings

        message = await self._client.messages.create(
            model=self._model,
            max_tokens=settings.llm_max_tokens,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": user}],
        )
        block = message.content[0]
        if not isinstance(block, TextBlock):
            raise RuntimeError(f"Unexpected content block type: {type(block).__name__}")

        meta = LLMCallMetadata(
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            finish_reason=message.stop_reason or "",
            model=message.model,
        )
        return block.text, meta


class StubLLMClient:
    """Minimal stub for unit tests — returns a configurable fixed response."""

    def __init__(self, response: str = '{"content": "stub response"}') -> None:
        self._response = response

    async def complete(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> str:
        return self._response
