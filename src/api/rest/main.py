"""FastAPI application entry point.

Spec: specs/system/architecture.md
ADR:  ADR-0002 (Technology Stack), ADR-0003 (Async API Strategy)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.rest.routers import health, hitl, requests
from src.observability.otel_setup import setup_telemetry
from src.shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_telemetry()
    yield


app = FastAPI(
    title="Enterprise AI System",
    version="0.1.0",
    description="Production-ready AI-powered system with HITL oversight.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(requests.router, prefix="/v1")
app.include_router(hitl.router, prefix="/v1/hitl")
