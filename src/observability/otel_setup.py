"""OpenTelemetry SDK bootstrap. Call setup_telemetry() once at application startup.

Spec: specs/system/architecture.md (Observability — Observable-by-default)
ADR:  ADR-0004 (Observability Stack)
"""

from __future__ import annotations

import atexit
import logging

from opentelemetry import metrics, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from src.shared.config import settings

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def setup_telemetry(
    service_name: str | None = None,
    service_version: str | None = None,
) -> None:
    """Initialise OpenTelemetry tracing, metrics, and propagation.

    Reads configuration from src.shared.config.settings. Safe to call multiple
    times — subsequent calls are no-ops once providers are initialised.
    """
    global _tracer_provider, _meter_provider

    if _tracer_provider is not None:
        return

    name = service_name or settings.otel_service_name
    version = service_version or settings.service_version
    environment = settings.app_env

    resource = Resource.create(
        {
            "service.name": name,
            "service.version": version,
            "deployment.environment": environment,
        }
    )

    # ── Tracing ───────────────────────────────────────────────────────────────
    span_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=environment != "production",
    )
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(_tracer_provider)

    # ── Metrics ───────────────────────────────────────────────────────────────
    metric_exporter = OTLPMetricExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=environment != "production",
    )
    reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60_000)
    _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(_meter_provider)

    # ── Propagation ───────────────────────────────────────────────────────────
    set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    atexit.register(_shutdown_telemetry)

    logger.info(
        "OpenTelemetry initialised",
        extra={"service": name, "version": version, "env": environment},
    )


def _shutdown_telemetry() -> None:
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
    if _meter_provider is not None:
        _meter_provider.shutdown()
