"""FastAPI application entry point.

Spec: specs/system/architecture.md
ADR:  ADR-0002 (Technology Stack), ADR-0003 (Async API Strategy)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as redis_async
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from slowapi.middleware import SlowAPIMiddleware

from src.agents.hitl_gateway import HITLGateway
from src.agents.hitl_store import HITLRedisStore, InMemoryHITLStore
from src.api.rest._limiter import limiter
from src.api.rest.errors import install_error_handlers
from src.api.rest.request_context import RequestContextMiddleware
from src.api.rest.routers import governance, health, hitl, requests, runs
from src.api.rest.security_headers import SecurityHeadersMiddleware
from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage, PostgresAuditStorage
from src.observability.metrics import init_budget_gauge
from src.observability.otel_setup import setup_telemetry
from src.shared.config import settings
from src.shared.db_client import ResilientDBPool
from src.shared.db_encryption import EncryptedField

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
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

    # Initialize Redis client with optional TLS (ADR-0019).
    # TLS is enabled when REDIS_TLS_ENABLED=true or the URL uses rediss:// scheme.
    try:
        _redis_kwargs: dict[str, object] = {
            "max_connections": settings.redis_max_connections,
            "decode_responses": True,
        }
        if settings.redis_tls_enabled or settings.redis_url.startswith("rediss://"):
            _redis_kwargs["ssl"] = True
            if settings.redis_tls_ca_cert:
                _redis_kwargs["ssl_ca_certs"] = settings.redis_tls_ca_cert
        _redis_client = redis_async.from_url(settings.redis_url, **_redis_kwargs)
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

    # Kafka broker — warn and continue if unavailable (local dev without Kafka).
    # Falls back to InMemoryBroker so the app starts cleanly; events are captured in-process.
    from src.shared.broker import InMemoryBroker, KafkaEventBroker

    try:
        _broker: KafkaEventBroker | InMemoryBroker = KafkaEventBroker(
            bootstrap_servers=settings.kafka_bootstrap_servers
        )
        await asyncio.wait_for(_broker.start(), timeout=10.0)
        app.state.broker = _broker
    except Exception as exc:
        logger.warning("Kafka producer unavailable — using InMemoryBroker: %s", exc)
        app.state.broker = InMemoryBroker()

    # Request store — Redis-backed when available; in-memory fallback for local dev.
    from src.agents.request_store import InMemoryRequestStore, RedisRequestStore

    if app.state.redis is not None:
        app.state.request_store = RedisRequestStore(client=app.state.redis)
    else:
        app.state.request_store = InMemoryRequestStore()

    # Idempotency-key store — same Redis/in-memory selection as the request store (ADR-0077).
    from src.agents.idempotency_store import (
        InMemoryIdempotencyStore,
        RedisIdempotencyStore,
    )

    if app.state.redis is not None:
        app.state.idempotency_store = RedisIdempotencyStore(client=app.state.redis)
    else:
        app.state.idempotency_store = InMemoryIdempotencyStore()

    # HITL gateway — Redis-backed when available; in-memory fallback for local dev.
    # Production pods must always have Redis available (see RB-003-hitl-recovery.md).
    # Payloads are AES-256-GCM encrypted at rest when db_encryption_enabled=True (ADR-0019).
    hitl_store: HITLRedisStore | InMemoryHITLStore
    if app.state.redis is not None:
        _hitl_encryption = (
            EncryptedField(settings.db_encryption_key)
            if settings.db_encryption_enabled
            and "placeholder" not in settings.db_encryption_key.lower()
            else None
        )
        hitl_store = HITLRedisStore(client=app.state.redis, encryption=_hitl_encryption)
    else:
        hitl_store = InMemoryHITLStore()
    app.state.hitl_gateway = HITLGateway(
        audit_logger=app.state.audit_logger,
        broker=app.state.broker,  # was always None; now wired to the real/in-memory broker
        store=hitl_store,
    )

    # Agent concurrency cap — limits simultaneous coroutines to prevent event-loop starvation
    app.state.agent_semaphore = asyncio.Semaphore(settings.max_concurrent_agents)

    # Request consumer background task — drives AgentOrchestrator for each queued request.
    # Skipped gracefully if Kafka is unavailable (consumer startup would fail the same way).
    from src.workers.request_consumer import RequestConsumer

    _consumer = RequestConsumer(
        store=app.state.request_store,
        audit_logger=app.state.audit_logger,
        hitl_gateway=app.state.hitl_gateway,
        broker=app.state.broker,  # REM-012: needed for DLQ publishing on exhausted retries
    )
    app.state.consumer_task = asyncio.create_task(_consumer.run())

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    # Brief sleep allows the load balancer to deregister this pod before
    # connections are torn down, preventing in-flight request drops.
    await asyncio.sleep(settings.shutdown_drain_seconds)

    # Cancel the consumer task and stop the Kafka producer cleanly.
    if hasattr(app.state, "consumer_task"):
        app.state.consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.consumer_task

    from src.shared.broker import KafkaEventBroker

    if isinstance(getattr(app.state, "broker", None), KafkaEventBroker):
        await app.state.broker.stop()

    if app.state.db_pool is not None:
        await app.state.db_pool.close()

    if app.state.redis is not None:
        await app.state.redis.aclose()


app = FastAPI(
    title="Enterprise API Gateway",
    version="0.1.0",
    description="Production-ready FastAPI gateway with optional AI Agents extension.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Structured error envelope for every non-2xx response, incl. rate-limit (429) and
# validation (422) — replaces FastAPI defaults (ADR-0076 / SPEC-API-001).
install_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# Security headers on every response (X-Content-Type-Options, X-Frame-Options,
# CSP, Referrer-Policy, Permissions-Policy; HSTS in production only).
app.add_middleware(SecurityHeadersMiddleware)
# Request correlation — added last so it is the OUTERMOST middleware: binds X-Request-ID
# before any handler logs and sets it on every response (ADR-0076).
app.add_middleware(RequestContextMiddleware)

# Prometheus metrics scrape endpoint — required for Golden Signals alert rules
app.mount("/metrics", make_asgi_app())

app.include_router(health.router)
app.include_router(requests.router, prefix="/v1")
# Read-only operator-UI views: per-request execution trace + SLO/error-budget panel (SPEC-API-004)
app.include_router(runs.router, prefix="/v1")
app.include_router(governance.router, prefix="/v1/governance")
# AI Agents Module — remove this router if src/agents/ is deleted
app.include_router(hitl.router, prefix="/v1/hitl")
