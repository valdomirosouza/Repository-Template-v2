"""Operator authentication & authorization for HITL endpoints.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Model)
Threat model: REM-001 (HITL operator impersonation)

Verifies a JWT **bearer** token (HS256 by default — ``settings.jwt_algorithm`` — signed with
``settings.secret_key``) and authorizes operators carrying the required role claim. The
authenticated subject (``sub``) is what the HITL gateway records as the ``approver_id`` in the
immutable audit trail, so a client can **no longer self-assert an approver identity** by putting
one in the request body.

> For multi-service / IdP deployments switch ``jwt_algorithm`` to an asymmetric scheme (RS256/
> ES256) and verify against the IdP's public key / JWKS. This module uses the symmetric secret
> appropriate to a single-service deployment.
"""

from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.shared.config import settings

_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


class Principal(BaseModel):
    """An authenticated caller derived from a verified JWT."""

    sub: str
    role: str | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_UNAUTHENTICATED_HEADERS,
    )


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Authenticate the caller from the ``Authorization: Bearer <jwt>`` header.

    Raises 401 if the token is missing, malformed, expired, or lacks a subject.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Missing bearer token")

    try:
        claims: dict[str, Any] = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise _unauthorized("Token missing subject")

    role = claims.get("role")
    return Principal(sub=sub, role=role if isinstance(role, str) else None)


def require_hitl_operator(
    principal: Principal = Depends(get_principal),
) -> Principal:
    """Authorize a HITL operator — requires the ``settings.hitl_operator_role`` claim.

    Raises 403 if the authenticated principal does not hold the operator role.
    """
    if principal.role != settings.hitl_operator_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator role '{settings.hitl_operator_role}' required",
        )
    return principal
