"""OTel wrapper for LLM clients — emits llm.inference spans with GenAI semantic conventions.

Spec: specs/observability/otel-agentic-observability.md §3.4
ADR:  ADR-0045

Usage::

    client = OtelLLMClientWrapper(AnthropicLLMClient())
    response = await client.complete(user="...", system="...", trace_id="t-1")

The wrapper:
1. Creates a child span named ``llm.inference`` under the active span.
2. Sets GenAI semantic convention attributes (gen_ai.system, gen_ai.request.*,
   gen_ai.usage.*, gen_ai.response.finish_reason).
3. Optionally attaches llm.prompt / llm.response span events when
   ``settings.otel_capture_prompts=True`` (debug only — stripped by Collector in production).
4. Records bounded Prometheus counters (llm_tokens_total by service/model/token_type — no
   per-request label; per-request cost lives on the span's gen_ai.usage.* attributes).
5. Works with any LLMClient; falls back gracefully when the inner client does not
   expose ``complete_with_metadata()``.
"""

from __future__ import annotations

import time

from opentelemetry.trace import StatusCode

from src.observability.metrics import record_llm_call
from src.observability.span_hierarchy import SPAN_LLM_INFERENCE, tracer
from src.shared.config import settings
from src.shared.llm_client import LLMCallMetadata, LLMClient


class OtelLLMClientWrapper:
    """Wraps any LLMClient and emits an ``llm.inference`` OTel span per call.

    Transparently satisfies the LLMClient protocol.
    """

    def __init__(self, inner: LLMClient, system_name: str = "anthropic") -> None:
        self._inner = inner
        self._system = system_name

    async def complete(
        self,
        user: str,
        system: str = "",
        trace_id: str | None = None,
    ) -> str:
        start = time.monotonic()

        with tracer.start_as_current_span(SPAN_LLM_INFERENCE) as span:
            span.set_attributes(
                {
                    "gen_ai.system": self._system,
                    "gen_ai.request.model": settings.llm_model,
                    "gen_ai.request.max_tokens": settings.llm_max_tokens,
                    "gen_ai.request.temperature": 1.0,
                }
            )

            if settings.otel_capture_prompts:
                span.add_event(
                    "llm.prompt",
                    {"content": user[:2000], "role": "user"},
                )

            try:
                text, meta = await self._call_inner(user=user, system=system, trace_id=trace_id)
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                raise

            duration = time.monotonic() - start

            span.set_attributes(
                {
                    "gen_ai.usage.input_tokens": meta.input_tokens,
                    "gen_ai.usage.output_tokens": meta.output_tokens,
                    "gen_ai.response.finish_reason": meta.finish_reason,
                }
            )

            if settings.otel_capture_prompts:
                span.add_event(
                    "llm.response",
                    {"content": text[:2000], "finish_reason": meta.finish_reason},
                )

            model = meta.model or settings.llm_model

            # Prometheus — record bounded token-usage and latency counters (no per-request
            # label). Per-request drill-down is via this call's OTel `llm.inference` span
            # (gen_ai.usage.* + trace_id), recorded above — not a high-cardinality metric label.
            record_llm_call(
                service=settings.otel_service_name,
                model=model,
                input_tokens=meta.input_tokens,
                output_tokens=meta.output_tokens,
                duration_seconds=duration,
            )

            return text

    async def _call_inner(
        self,
        user: str,
        system: str,
        trace_id: str | None,
    ) -> tuple[str, LLMCallMetadata]:
        from src.shared.llm_client import AnthropicLLMClient

        if isinstance(self._inner, AnthropicLLMClient):
            return await self._inner.complete_with_metadata(
                user=user, system=system, trace_id=trace_id
            )

        # Fallback for any LLMClient that doesn't expose complete_with_metadata
        if hasattr(self._inner, "complete_with_metadata"):
            result: tuple[str, LLMCallMetadata] = await self._inner.complete_with_metadata(
                user=user, system=system, trace_id=trace_id
            )
            return result

        text = await self._inner.complete(user=user, system=system, trace_id=trace_id)
        return text, LLMCallMetadata()
