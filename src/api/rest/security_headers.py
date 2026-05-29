"""HTTP security response headers middleware.

Adds defence-in-depth headers to every API response. HSTS is gated on
app_env=production so local development over HTTP is not broken.

Spec: specs/api/rest-api-design.md (Security Headers)
ADR:  ADR-0002 (Technology Stack Selection)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.shared.config import settings

# Content-Security-Policy for a pure JSON API: block all resource loading.
# If you add a Swagger UI (docs_url) in non-production, add 'self' and the
# CDN origins used by Swagger's CSS/JS to the relevant directives.
_CSP_API_ONLY = "default-src 'none'; frame-ancestors 'none'; form-action 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects security headers on every response.

    Headers applied unconditionally:
      X-Content-Type-Options     — prevents MIME-type sniffing attacks
      X-Frame-Options            — prevents clickjacking via iframe embedding
      Referrer-Policy            — limits referrer leakage to same-origin only
      Permissions-Policy         — disables browser APIs the API never uses
      Content-Security-Policy    — blocks all resource loading (API-only policy)

    Production-only header:
      Strict-Transport-Security  — only sent over HTTPS; 2-year max-age
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = _CSP_API_ONLY

        if settings.app_env == "production":
            # 2-year max-age with subdomains + preload — HSTS only meaningful over TLS.
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response
