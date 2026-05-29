"""Shared slowapi Limiter instance.

Spec: specs/api/rest-api-design.md (Rate Limiting)
ADR:  ADR-0002 (Technology Stack Selection)

Import this module (not slowapi directly) to ensure a single Limiter instance
is shared between main.py (middleware registration) and routers (decorators).
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_rate_limit_key(request: Request) -> str:
    """Rate-limit by JWT subject when present, fall back to remote IP.

    The JWT is decoded *without* signature verification — intentionally.
    This is for traffic bucketing, not authentication. A client could craft
    a JWT with any sub to land in a different bucket, but they would still
    hit the same per-bucket limit, and the real auth check downstream rejects
    invalid tokens before any privileged operation occurs.

    Result: one rate-limit bucket per authenticated user (sub) and one shared
    bucket per unauthenticated IP, preventing a single IP from exhausting the
    limit across multiple accounts.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            import jwt as pyjwt  # lazy: PyJWT is optional for test environments

            payload = pyjwt.decode(token, options={"verify_signature": False})
            sub = str(payload.get("sub", ""))
            if sub:
                return f"subject:{sub}"
        except Exception:  # noqa: S110 — intentional: JWT failures fall back to IP silently
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_get_rate_limit_key)
