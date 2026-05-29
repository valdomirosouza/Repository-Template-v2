"""__SERVICE_NAME__ — FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, make_asgi_app

from .__MODULE_NAME__.config import settings

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "status"],
)


def _setup_telemetry() -> None:
    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    _setup_telemetry()
    yield


app = FastAPI(
    title="__SERVICE_NAME__",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
async def ready() -> dict[str, str]:
    # TODO: add dependency checks (DB, Redis, etc.)
    return {"status": "ready"}
