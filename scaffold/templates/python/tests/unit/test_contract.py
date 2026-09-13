"""API contract test (scaffold starter, W15-T5).

The service's live OpenAPI schema must expose the two probe endpoints every service in
services.yaml promises (`/health`, `/ready`) and the Prometheus scrape endpoint. Extend this
file with the service's own contract (pact/OpenAPI) as endpoints are added.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from __MODULE_NAME__.main import app


def test_openapi_exposes_the_probe_endpoints() -> None:
    paths = set(app.openapi()["paths"])
    assert {"/health", "/ready"} <= paths


@pytest.mark.asyncio
async def test_metrics_endpoint_is_scrapable() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/metrics", follow_redirects=True)  # the mount redirects to /metrics/
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "# HELP" in resp.text  # exposition format; the service's own counters appear once observed
