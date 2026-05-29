"""Unit tests for SecurityHeadersMiddleware.

Spec: specs/api/rest-api-design.md (Security Headers)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from src.api.rest.security_headers import SecurityHeadersMiddleware


def _make_app(env: str = "development"):
    from fastapi import FastAPI
    from starlette.responses import JSONResponse

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return JSONResponse({"ok": True})

    return app


class TestSecurityHeadersAlways:
    def test_x_content_type_options_present(self) -> None:
        client = TestClient(_make_app())
        response = client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_deny(self) -> None:
        client = TestClient(_make_app())
        response = client.get("/test")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy_set(self) -> None:
        client = TestClient(_make_app())
        response = client.get("/test")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_set(self) -> None:
        client = TestClient(_make_app())
        response = client.get("/test")
        assert "geolocation=()" in response.headers["Permissions-Policy"]

    def test_content_security_policy_set(self) -> None:
        client = TestClient(_make_app())
        response = client.get("/test")
        assert "default-src 'none'" in response.headers["Content-Security-Policy"]


class TestSecurityHeadersProduction:
    def test_hsts_absent_in_development(self) -> None:
        with patch("src.api.rest.security_headers.settings") as mock_settings:
            mock_settings.app_env = "development"
            client = TestClient(_make_app("development"))
            response = client.get("/test")
            assert "Strict-Transport-Security" not in response.headers

    def test_hsts_present_in_production(self) -> None:
        with patch("src.api.rest.security_headers.settings") as mock_settings:
            mock_settings.app_env = "production"
            client = TestClient(_make_app("production"))
            response = client.get("/test")
            assert "max-age=63072000" in response.headers.get("Strict-Transport-Security", "")
            assert "includeSubDomains" in response.headers["Strict-Transport-Security"]


pyjwt = pytest.importorskip("jwt", reason="PyJWT not installed in this venv")


class TestRateLimitKeyFunc:
    def test_falls_back_to_ip_without_auth(self) -> None:
        from src.api.rest._limiter import _get_rate_limit_key

        request = MagicMock()
        request.headers = {}
        request.client.host = "1.2.3.4"

        key = _get_rate_limit_key(request)
        assert key.startswith("ip:")

    def test_uses_jwt_sub_when_valid_bearer(self) -> None:
        from src.api.rest._limiter import _get_rate_limit_key

        token = pyjwt.encode({"sub": "user-abc-123"}, "secret", algorithm="HS256")

        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client.host = "1.2.3.4"

        key = _get_rate_limit_key(request)
        assert key == "subject:user-abc-123"

    def test_falls_back_to_ip_with_malformed_token(self) -> None:
        from src.api.rest._limiter import _get_rate_limit_key

        request = MagicMock()
        request.headers = {"Authorization": "Bearer not.a.jwt"}
        request.client.host = "5.6.7.8"

        key = _get_rate_limit_key(request)
        assert key.startswith("ip:")

    def test_falls_back_to_ip_with_no_sub_claim(self) -> None:
        from src.api.rest._limiter import _get_rate_limit_key

        token = pyjwt.encode({"exp": 9999999999}, "secret", algorithm="HS256")

        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {token}"}
        request.client.host = "1.2.3.4"

        key = _get_rate_limit_key(request)
        assert key.startswith("ip:")
