"""Structured JSON logger with mandatory PII masking on every log record.

Spec: specs/ai/guardrails.md (Layer 1 — pre-log write interception point)
ADR:  ADR-0004 (Observability Stack), ADR-0012 (PII Masking Strategy)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from src.observability.request_context import get_request_id
from src.shared.config import settings

# pii_filter is created in prompt 010; import is forward-declared here.
# At runtime the module must be present before any log is written.
try:
    from src.guardrails.pii_filter import mask_dict as _mask_dict
except ImportError:  # during initial scaffold / unit tests without guardrails

    def _mask_dict(data: dict[str, object]) -> dict[str, object]:  # type: ignore[misc]
        return data


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = record.__dict__.get("_structured_payload", {})
        return json.dumps(payload, default=str, ensure_ascii=False)


class StructuredLogger:
    """Emits structured JSON log records with PII masking and OTel trace context."""

    def __init__(self, service: str, component: str) -> None:
        self._service = service
        self._component = component
        self._logger = logging.getLogger(f"{service}.{component}")

    def _build_record(
        self,
        severity: str,
        message: str,
        context: dict[str, Any],
        mask: bool = True,
    ) -> dict[str, Any]:
        span = trace.get_current_span()
        span_ctx = span.get_span_context()

        safe_context = _mask_dict(context) if mask and settings.pii_masking_enabled else context

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": severity,
            "service": self._service,
            "component": self._component,
            "message": message,
            "trace_id": format(span_ctx.trace_id, "032x") if span_ctx.is_valid else None,
            "span_id": format(span_ctx.span_id, "016x") if span_ctx.is_valid else None,
            "request_id": get_request_id(),
            **safe_context,
        }

    def _emit(self, level: int, payload: dict[str, Any]) -> None:
        record = logging.LogRecord(
            name=self._logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        record.__dict__["_structured_payload"] = payload
        self._logger.handle(record)

    def debug(self, message: str, **context: Any) -> None:
        self._emit(logging.DEBUG, self._build_record("DEBUG", message, context))

    def info(self, message: str, **context: Any) -> None:
        self._emit(logging.INFO, self._build_record("INFO", message, context))

    def warning(self, message: str, **context: Any) -> None:
        self._emit(logging.WARNING, self._build_record("WARNING", message, context))

    def error(self, message: str, exc_info: bool = False, **context: Any) -> None:
        payload = self._build_record("ERROR", message, context)
        if exc_info:
            import traceback

            payload["exception"] = traceback.format_exc()
        self._emit(logging.ERROR, payload)

    def audit(self, event: str, **context: Any) -> None:
        """Write to the audit stream. Context fields are NOT masked — identifiers
        required for legal traceability are preserved in the audit log only."""
        payload = self._build_record("AUDIT", event, context, mask=False)
        self._emit(logging.INFO, payload)


def _configure_root_logger() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


_configure_root_logger()


def get_logger(component: str) -> StructuredLogger:
    """Factory — returns a StructuredLogger bound to the configured service name."""
    return StructuredLogger(service=settings.service_name, component=component)
