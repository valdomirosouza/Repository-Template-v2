"""Health and readiness endpoints.

Spec: specs/system/architecture.md
ADR:  ADR-0002 (Technology Stack)

These endpoints are used by:
- Kubernetes liveness and readiness probes
- smoke-test.sh post-deploy verification
- HAProxy / load balancer health checks
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from src.shared.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Returns 200 if the process is alive. No dependency checks."""
    return HealthResponse(status="ok", version=settings.service_version)


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def ready(request: Request) -> HealthResponse:
    """Returns 200 only when DB and Redis are reachable.

    Returns 503 if any dependency is unreachable, signalling Kubernetes not to
    route traffic to this pod until it is fully initialised.
    """
    db_pool = getattr(request.app.state, "db_pool", None)
    redis = getattr(request.app.state, "redis", None)

    if db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DB pool not initialised",
        )
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client not initialised",
        )

    try:
        await asyncio.wait_for(db_pool.fetchval("SELECT 1"), timeout=2.0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"DB unreachable: {exc}",
        ) from exc

    try:
        await asyncio.wait_for(redis.ping(), timeout=2.0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis unreachable: {exc}",
        ) from exc

    return HealthResponse(status="ready", version=settings.service_version)
