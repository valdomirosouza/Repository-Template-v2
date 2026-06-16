"""Unit tests for the governance router — GET /v1/governance/slo-status.

Spec: specs/api/SPEC-API-004-runs-trace-and-slo-status.md
ADR:  ADR-0076 (structured error model), ADR-0004 (observability)

Asserts the endpoint returns the yaml-defined SLOs and the HONEST data-availability flags;
it never fabricates observed numbers (CLAUDE.md §3.6).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.rest.errors import install_error_handlers
from src.api.rest.routers.governance import load_slo_definitions, router
from src.observability.metrics import REQUEST_COUNTER
from src.shared.config import settings

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(router, prefix="/v1/governance")
    return app


def _token(sub: str = "viewer-01", role: str | None = "viewer", expires_in: int = 3600) -> str:
    payload: dict = {"sub": sub, "exp": datetime.now(UTC) + timedelta(seconds=expires_in)}
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _auth() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestSLOStatusAuth:
    @pytest.mark.asyncio
    async def test_rejects_missing_token(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/governance/slo-status")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"


# ── Behaviour ───────────────────────────────────────────────────────────────────


class TestSLOStatus:
    @pytest.mark.asyncio
    async def test_returns_all_yaml_defined_slos(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/governance/slo-status", headers=_auth())

        assert response.status_code == 200
        body = response.json()

        # Source matches the parsed yaml exactly — no invented services/SLOs.
        defs = load_slo_definitions()
        expected_services = {s["name"] for s in defs["services"]}
        returned_services = {s["name"] for s in body["services"]}
        assert returned_services == expected_services

        expected_total = sum(len(s["slos"]) for s in defs["services"])
        returned_total = sum(len(s["slos"]) for s in body["services"])
        assert returned_total == expected_total
        assert body["source_version"] == str(defs["version"])

    @pytest.mark.asyncio
    async def test_targets_come_straight_from_yaml(self) -> None:
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/governance/slo-status", headers=_auth())
        body = response.json()

        api_gateway = next(s for s in body["services"] if s["name"] == "api-gateway")
        availability = next(s for s in api_gateway["slos"] if s["name"] == "availability")
        assert availability["target"] == 99.9
        assert availability["window"] == "30d"
        latency = next(s for s in api_gateway["slos"] if s["name"] == "latency_p99")
        assert latency["target_ms"] == 500

    @pytest.mark.asyncio
    async def test_non_computable_slos_flagged_not_fabricated(self) -> None:
        """Latency / saturation / agent SLOs have no in-process value → data_available false."""
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/governance/slo-status", headers=_auth())
        body = response.json()

        api_gateway = next(s for s in body["services"] if s["name"] == "api-gateway")
        latency = next(s for s in api_gateway["slos"] if s["name"] == "latency_p99")
        assert latency["observed"]["data_available"] is False
        assert latency["observed"]["note"]  # explains why
        assert latency["observed"].get("value") is None  # never fabricated

    @pytest.mark.asyncio
    async def test_api_gateway_availability_uses_real_in_process_counter(self) -> None:
        """When the http_requests_total counter has api-gateway samples, observed is real and
        scoped as a process-lifetime sample (not the 30-day SLO window)."""
        # Seed the real Prometheus counter with synthetic api-gateway traffic.
        REQUEST_COUNTER.labels("api-gateway", "GET", "/v1/runs", "200").inc(9)
        REQUEST_COUNTER.labels("api-gateway", "GET", "/v1/runs", "500").inc(1)

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/governance/slo-status", headers=_auth())
        body = response.json()

        api_gateway = next(s for s in body["services"] if s["name"] == "api-gateway")
        availability = next(s for s in api_gateway["slos"] if s["name"] == "availability")
        observed = availability["observed"]
        assert observed["data_available"] is True
        assert observed["scope"] == "process_lifetime"
        assert observed["unit"] == "percent"
        assert observed["source"].startswith("prometheus:")
        # Value is a real share of non-5xx in [0, 100], not an invented SLO figure.
        assert 0.0 <= observed["value"] <= 100.0
