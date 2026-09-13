"""Production LLM client factory (W12-T3, issue #356).

The resilience and observability wrappers existed but nothing constructed them: the request
consumer built a bare ``AnthropicLLMClient()`` per retry attempt, so ``llm_call_timeout_seconds``,
the retry policy and the circuit breaker were dead configuration and ``llm.inference`` spans /
token metrics never fired. Every production caller now goes through :func:`build_llm_client`.

Stack (outermost first)::

    OtelLLMClientWrapper            # llm.inference span + gen_ai.* attributes (ADR-0044/0045)
      └─ ResilientLLMClientWrapper  # retry + circuit breaker (ADR-0075)
           └─ TimeoutLLMClientWrapper   # asyncio.wait_for ceiling (built by Resilient)
                └─ AnthropicLLMClient   # or an injected base client (tests)

Spec: specs/ai/agent-design.md · ADR-0044, ADR-0045, ADR-0075
"""

from __future__ import annotations

from src.agents.llm_client_otel import OtelLLMClientWrapper
from src.shared.config import settings
from src.shared.llm_client import AnthropicLLMClient, LLMClient
from src.shared.retry import CircuitBreaker, ResilientLLMClientWrapper


def build_llm_client(base: LLMClient | None = None) -> LLMClient:
    """Return the fully wrapped production client.

    ``base`` lets tests and the wiring test inject a ``StubLLMClient`` while still exercising
    the real wrapper stack. The circuit breaker is created here so one breaker is shared by all
    calls made through this client for the life of the consumer.
    """
    inner: LLMClient = base if base is not None else AnthropicLLMClient()
    resilient = ResilientLLMClientWrapper(
        inner,
        timeout_seconds=settings.llm_call_timeout_seconds,
        circuit_breaker=CircuitBreaker(
            name="llm",
            threshold=settings.llm_circuit_breaker_threshold,
            reset_seconds=settings.llm_circuit_breaker_reset_seconds,
        ),
    )
    return OtelLLMClientWrapper(resilient, system_name="anthropic")


def unwrap_stack(client: LLMClient) -> list[str]:
    """Class names from the outermost wrapper inwards — used by the lifespan wiring test."""
    names: list[str] = []
    current: object = client
    while current is not None:
        names.append(type(current).__name__)
        current = getattr(current, "_inner", None) or getattr(current, "_client", None)
        if len(names) > 8:  # defensive: never loop on a self-referential object
            break
    return names
