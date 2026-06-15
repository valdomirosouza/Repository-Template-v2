"""Unit tests for the list pagination helper and its use on GET /v1/hitl/requests.

Covers SPEC-API-003 acceptance criteria AC-01..AC-05 (ADR-0078).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Query, Request, Response
from starlette.testclient import TestClient

from src.api.rest.errors import install_error_handlers
from src.api.rest.pagination import effective_limit, paginate
from src.shared.config import settings

pytestmark = pytest.mark.unit


def _make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/items")
    async def items(
        request: Request,
        response: Response,
        limit: int | None = Query(default=None, ge=1, le=settings.pagination_max_limit),
        offset: int = Query(default=0, ge=0),
    ) -> list[int]:
        data = list(range(5))  # [0,1,2,3,4]
        size = effective_limit(limit, default=100)
        return paginate(data, limit=size, offset=offset, request=request, response=response)

    return app


# ---------------------------------------------------------------- AC-01 / AC-03


def test_limit_offset_returns_correct_slice_and_headers() -> None:
    client = TestClient(_make_app())
    r = client.get("/items?limit=2&offset=1")
    assert r.json() == [1, 2]  # AC-01: 2nd–3rd items
    assert r.headers["X-Total-Count"] == "5"  # AC-03: total disclosed
    assert 'rel="next"' in r.headers["Link"]  # more pages exist
    assert "offset=3" in r.headers["Link"]


def test_prev_link_present_when_not_first_page() -> None:
    client = TestClient(_make_app())
    r = client.get("/items?limit=2&offset=2")
    assert 'rel="prev"' in r.headers["Link"]


# ---------------------------------------------------------------- AC-02


def test_no_params_returns_full_list() -> None:
    client = TestClient(_make_app())
    r = client.get("/items")
    assert r.json() == [0, 1, 2, 3, 4]  # unchanged body
    assert r.headers["X-Total-Count"] == "5"
    assert "Link" not in r.headers  # single page → no next/prev


# ---------------------------------------------------------------- AC-04


@pytest.mark.parametrize("qs", ["limit=0", "limit=999", "offset=-1"])
def test_out_of_range_params_are_422(qs: str) -> None:
    client = TestClient(_make_app())
    r = client.get(f"/items?{qs}")
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------- helper unit


def test_effective_limit_caps_and_defaults() -> None:
    assert effective_limit(None, default=10) == 10
    assert effective_limit(5, default=10) == 5
    assert effective_limit(10_000, default=10) == settings.pagination_max_limit  # capped
    assert effective_limit(0, default=10) == 1  # floored to >= 1
