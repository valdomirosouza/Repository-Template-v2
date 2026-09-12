"""Unit tests for src/api/rest/auth.py — the JWT operator surface (W15-T1, issue #388).

Spec: specs/security/rbac-model.md · ADR-0011 · REM-001 (approver impersonation)

The module had zero referencing tests. These cover every rejection branch and the happy path
through a minimal FastAPI app so the HTTP status codes and WWW-Authenticate header are real.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.rest.auth import Principal, get_principal, require_hitl_operator
from src.shared.config import settings

pytestmark = [pytest.mark.unit, pytest.mark.requirement("SPEC-SEC-002")]

SUB = "operator-00000000-0000-0000-0000-000000000001"


def _token(
    *,
    sub: str | None = SUB,
    role: str | None = None,
    expires_in: int = 3600,
    secret: str | None = None,
    algorithm: str | None = None,
    include_exp: bool = True,
) -> str:
    payload: dict[str, Any] = {}
    if sub is not None:
        payload["sub"] = sub
    if include_exp:
        payload["exp"] = datetime.now(UTC) + timedelta(seconds=expires_in)
    if role is not None:
        payload["role"] = role
    return jwt.encode(
        payload, secret or settings.secret_key, algorithm=algorithm or settings.jwt_algorithm
    )


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/who")
    async def who(p: Principal = Depends(get_principal)) -> dict[str, Any]:
        return {"sub": p.sub, "role": p.role}

    @app.get("/operator")
    async def operator(p: Principal = Depends(require_hitl_operator)) -> dict[str, str]:
        return {"sub": p.sub}

    return app


async def _get(path: str, token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as c:
        return await c.get(path, headers=headers)


async def test_valid_token_yields_principal_with_role():
    r = await _get("/who", _token(role="viewer"))
    assert r.status_code == 200
    assert r.json() == {"sub": SUB, "role": "viewer"}


async def test_missing_token_is_401_with_www_authenticate():
    r = await _get("/who", None)
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"
    assert r.json()["detail"] == "Missing bearer token"


async def test_empty_bearer_is_401():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as c:
        r = await c.get("/who", headers={"Authorization": "Bearer "})
    assert r.status_code == 401


async def test_expired_token_is_401():
    r = await _get("/who", _token(expires_in=-10))
    assert r.status_code == 401
    assert r.json()["detail"] == "Token expired"


async def test_token_without_exp_is_rejected():
    """`exp` is required (options.require) — a token that never expires is invalid."""
    r = await _get("/who", _token(include_exp=False))
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


async def test_wrong_secret_is_401():
    r = await _get("/who", _token(secret="x" * 40))
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


async def test_token_missing_subject_is_401():
    r = await _get("/who", _token(sub=None))
    assert r.status_code == 401


async def test_non_string_subject_is_401():
    token = jwt.encode(
        {"sub": 12345, "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = await _get("/who", token)
    assert r.status_code == 401


async def test_non_string_role_is_normalised_to_none():
    token = jwt.encode(
        {"sub": SUB, "role": ["hitl-operator"], "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = await _get("/who", token)
    assert r.status_code == 200 and r.json()["role"] is None


async def test_malformed_token_is_401():
    r = await _get("/who", "not.a.jwt")
    assert r.status_code == 401


async def test_operator_role_required_403_when_absent_or_wrong():
    assert (await _get("/operator", _token())).status_code == 403
    assert (await _get("/operator", _token(role="viewer"))).status_code == 403
    r = await _get("/operator", _token(role=settings.hitl_operator_role))
    assert r.status_code == 200 and r.json()["sub"] == SUB


async def test_operator_dependency_still_requires_authentication_first():
    r = await _get("/operator", None)
    assert r.status_code == 401  # authn before authz


def test_principal_model_is_strict_about_sub():
    with pytest.raises(Exception):
        Principal(sub=None)  # type: ignore[arg-type]
