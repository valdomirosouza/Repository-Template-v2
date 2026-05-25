"""FastAPI application entry point.

Spec: specs/system/architecture.md
ADR:  ADR-0002 (Technology Stack), ADR-0003 (Async API Strategy)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis_async
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.agents.hitl_gateway import HITLGateway
from src.api.rest._limiter import limiter
from src.api.rest.routers import health, hitl, requests
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage, PostgresAuditStorage
from src.observability.metrics import init_budget_gauge
from src.observability.otel_setup import setup_telemetry
from src.shared.config import settings
from src.shared.db_client import ResilientDBPool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ───────────────────────────────────────────────────────────────
    setup_telemetry()
    init_budget_gauge(settings.service_name, settings.llm_monthly_token_budget)

    # Wire OTel HTTP instrumentation after app is created
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument_app(app, excluded_urls="/health,/ready,/metrics")
    except Exception as exc:
        logger.warning("OTel FastAPI instrumentation failed: %s", exc)

    # Initialize DB connection pool (15 s hard timeout prevents infinite boot loops).
    # Wrapped in ResilientDBPool to add per-call timeout, retry, and circuit breaker.
    try:
        _raw_pool = await asyncio.wait_for(
            asyncpg.create_pool(
                settings.database_url,
                min_size=2,
                max_size=settings.database_pool_size,
            ),
            timeout=15.0,
        )
        app.state.db_pool = ResilientDBPool(_raw_pool)
    except Exception as exc:
        logger.warning("DB pool creation failed — readiness will return 503: %s", exc)
        app.state.db_pool = None

    # Initialize Redis client (5 s ping timeout)
    try:
        _redis_client = redis_async.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
        await asyncio.wait_for(_redis_client.ping(), timeout=5.0)
        app.state.redis = _redis_client
    except Exception as exc:
        logger.warning("Redis client creation failed — readiness will return 503: %s", exc)
        app.state.redis = None

    # Use durable PostgresAuditStorage when the pool is available; fall back to
    # InMemoryAuditStorage only when no DB connection could be established (tests,
    # local dev without a running database). Production must never use the
    # in-memory backend — audit records would be lost on pod restart.
    if app.state.db_pool is not None:
        app.state.audit_logger = AuditLogger(PostgresAuditStorage(pool=app.state.db_pool))
    else:
        if settings.app_env == "production":
            raise RuntimeError(
                "DB pool unavailable in production: audit logger cannot use "
                "InMemoryAuditStorage — audit records would be lost on pod restart."
            )
        app.state.audit_logger = AuditLogger(InMemoryAuditStorage())

    # HITL gateway — wired to the audit logger
    app.state.hitl_gateway = HITLGateway(
        audit_logger=app.state.audit_logger,
        broker=None,
    )

    # Agent concurrency cap — limits simultaneous coroutines to prevent event-loop starvation
    app.state.agent_semaphore = asyncio.Semaphore(settings.max_concurrent_agents)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    # Brief sleep allows the load balancer to deregister this pod before
    # connections are torn down, preventing in-flight request drops.
    await asyncio.sleep(settings.shutdown_drain_seconds)

    if app.state.db_pool is not None:
        await app.state.db_pool.close()

    if app.state.redis is not None:
        await app.state.redis.aclose()


app = FastAPI(
    title="Enterprise AI System",
    version="0.1.0",
    description="Production-ready AI-powered system with HITL oversight.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Prometheus metrics scrape endpoint — required for Golden Signals alert rules
app.mount("/metrics", make_asgi_app())

app.include_router(health.router)
app.include_router(requests.router, prefix="/v1")
app.include_router(hitl.router, prefix="/v1/hitl")
