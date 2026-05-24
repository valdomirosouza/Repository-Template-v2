"""Health and readiness endpoints.

Spec: specs/system/architecture.md
ADR:  ADR-0002 (Technology Stack)

These endpoints are used by:
- Kubernetes liveness and readiness probes
- smoke-test.sh post-deploy verification
- HAProxy / load balancer health checks
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Returns 200 if the process is alive. No dependency checks."""
    from src.shared.config import settings
    return HealthResponse(status="ok", version=settings.service_version)


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def ready() -> HealthResponse:
    """Returns 200 if the service is ready to accept traffic.

    In production, extend this to check DB connectivity and Kafka reachability
    before returning ready — prevents traffic routing to a half-started pod.
    """
    from src.shared.config import settings
    return HealthResponse(status="ready", version=settings.service_version)
