"""Unit tests for health and readiness endpoints.

Spec: specs/system/architecture.md, specs/k8s/probe-strategy.md §3.1
ADR:  ADR-0002 (Technology Stack), ADR-0042 (K8s Probe Strategy)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.rest.routers.health import router


def _make_app(db_pool: object = None, redis: object = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = db_pool
    app.state.redis = redis
    return app


class TestProbeCompliance:
    """Verify probe-strategy spec §3.1: /health must never check dependencies."""

    @pytest.mark.asyncio
    async def test_health_returns_200_when_db_pool_is_none(self) -> None:
        app = _make_app(db_pool=None, redis=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200, "/health must return 200 even when DB is unavailable"

    @pytest.mark.asyncio
    async def test_health_returns_200_when_redis_is_none(self) -> None:
        app = _make_app(db_pool=None, redis=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200, "/health must return 200 even when Redis is unavailable"

    @pytest.mark.asyncio
    async def test_ready_returns_503_not_500_when_db_down(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_db.fetchval = AsyncMock(side_effect=OSError("db down"))
        mock_redis = AsyncMock()
        app = _make_app(db_pool=mock_db, redis=mock_redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 503, (
            "/ready must signal 503 (not 500) for K8s readiness probe"
        )


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_ok_status(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_response_contains_version(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert "version" in response.json()


class TestReadyEndpointDependencyChecks:
    @pytest.mark.asyncio
    async def test_returns_503_when_db_pool_is_none(self) -> None:
        app = _make_app(db_pool=None, redis=AsyncMock())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_503_when_redis_is_none(self) -> None:
        mock_db = AsyncMock()
        mock_db.fetchval.return_value = 1
        app = _make_app(db_pool=mock_db, redis=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_200_when_both_dependencies_healthy(self) -> None:
        mock_db = AsyncMock()
        mock_db.fetchval.return_value = 1
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        app = _make_app(db_pool=mock_db, redis=mock_redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_503_when_db_unreachable(self) -> None:
        mock_db = MagicMock()
        mock_db.fetchval = AsyncMock(side_effect=OSError("connection refused"))
        mock_redis = AsyncMock()
        app = _make_app(db_pool=mock_db, redis=mock_redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_503_when_redis_unreachable(self) -> None:
        mock_db = AsyncMock()
        mock_db.fetchval.return_value = 1
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(side_effect=OSError("connection refused"))
        app = _make_app(db_pool=mock_db, redis=mock_redis)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 503
