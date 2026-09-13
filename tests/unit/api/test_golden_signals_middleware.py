"""Unit tests for src/api/rest/middleware/golden_signals.py (W12-T4, FEAT-001).

`http_requests_total` / `http_request_duration_seconds` were defined and never populated.
The middleware records method, *route template* (never the raw path), status and duration.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from src.api.rest.middleware.golden_signals import GoldenSignalsMiddleware, route_template
from src.observability.metrics import REQUEST_COUNTER, REQUEST_LATENCY

pytestmark = pytest.mark.unit

SERVICE = "svc-under-test"


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(GoldenSignalsMiddleware, service=SERVICE)

    @app.get("/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        if item_id == "boom":
            raise HTTPException(status_code=418)
        if item_id == "crash":
            raise RuntimeError("unhandled")
        return {"id": item_id}

    @app.get("/metrics")
    async def metrics() -> dict[str, str]:
        return {"excluded": "yes"}

    return app


def _count(method: str, path: str, status: str) -> float:
    return REQUEST_COUNTER.labels(SERVICE, method, path, status)._value.get()


async def test_records_route_template_not_raw_path():
    before = _count("GET", "/items/{item_id}", "200")
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as c:
        assert (await c.get("/items/00000000-0000-0000-0000-000000000042")).status_code == 200
    assert _count("GET", "/items/{item_id}", "200") == before + 1
    # the raw identifier never becomes a label value
    assert _count("GET", "/items/00000000-0000-0000-0000-000000000042", "200") == 0


async def test_records_error_status_and_unmatched_routes():
    before_418 = _count("GET", "/items/{item_id}", "418")
    before_404 = _count("GET", "<unmatched>", "404")
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as c:
        assert (await c.get("/items/boom")).status_code == 418
        assert (await c.get("/nope")).status_code == 404
    assert _count("GET", "/items/{item_id}", "418") == before_418 + 1
    assert _count("GET", "<unmatched>", "404") == before_404 + 1


async def test_unhandled_exception_counts_as_500_and_propagates():
    before = _count("GET", "/items/{item_id}", "500")
    async with AsyncClient(
        transport=ASGITransport(app=_app(), raise_app_exceptions=False), base_url="http://t"
    ) as c:
        assert (await c.get("/items/crash")).status_code == 500
    assert _count("GET", "/items/{item_id}", "500") == before + 1


async def test_metrics_endpoint_is_excluded_and_latency_observed():
    before = _count("GET", "/metrics", "200")
    hist_before = REQUEST_LATENCY.labels(SERVICE, "GET", "/items/{item_id}")._sum.get()
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as c:
        await c.get("/metrics")
        await c.get("/items/x")
    assert _count("GET", "/metrics", "200") == before
    assert REQUEST_LATENCY.labels(SERVICE, "GET", "/items/{item_id}")._sum.get() > hist_before


def test_route_template_falls_back_when_unrouted():
    assert route_template({}) == "<unmatched>"
    assert route_template({"route": object()}) == "<unmatched>"
