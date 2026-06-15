"""Domain request submission and status endpoints.

Flow: POST /v1/requests → validate → mask PII → save state → publish domain.request.created → 202
      GET  /v1/requests/{id} → query state store → 200 with current status (polling model)

Spec: specs/system/request-pipeline.md, specs/system/async-event-flow.md
ADR:  ADR-0002 (Technology Stack), ADR-0003 (Async API Strategy)
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.agents.idempotency_store import (
    IdempotencyRecord,
    IdempotencyStoreProtocol,
    fingerprint_body,
)
from src.agents.request_store import RequestState, RequestStoreProtocol
from src.api.rest._limiter import limiter
from src.api.rest.errors import AppError
from src.guardrails.pii_filter import mask_dict
from src.observability.logger import get_logger
from src.observability.metrics import AGENT_SEMAPHORE_WAITING
from src.shared.broker import EventBrokerProtocol, build_envelope
from src.shared.config import settings

logger = get_logger("api.requests")
router = APIRouter(tags=["requests"])


# ── Request / response models ─────────────────────────────────────────────────


class RequestIn(BaseModel):
    request_text: str = Field(..., min_length=1, max_length=4000)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")


class RequestOut(BaseModel):
    request_id: str
    status: str
    created_at: datetime
    message: str


class RequestStatusResponse(BaseModel):
    request_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None
    message: str


# ── Dependencies ──────────────────────────────────────────────────────────────


def get_request_store(request: Request) -> RequestStoreProtocol:
    """FastAPI dependency: resolves RequestStore from app.state."""
    store: RequestStoreProtocol | None = getattr(request.app.state, "request_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Request store unavailable — service initialising",
        )
    return store


def get_event_broker(request: Request) -> EventBrokerProtocol:
    """FastAPI dependency: resolves EventBroker from app.state."""
    broker: EventBrokerProtocol | None = getattr(request.app.state, "broker", None)
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event broker unavailable — service initialising",
        )
    return broker


def get_idempotency_store(request: Request) -> IdempotencyStoreProtocol:
    """FastAPI dependency: resolves the idempotency-key store from app.state (ADR-0077).

    Degrade-open (ADR-0075): if no store was wired (Redis down, or a minimal app), fall back to a
    per-app in-memory store so submissions still work — correctness is then per-instance.
    """
    store: IdempotencyStoreProtocol | None = getattr(request.app.state, "idempotency_store", None)
    if store is None:
        from src.agents.idempotency_store import InMemoryIdempotencyStore

        store = InMemoryIdempotencyStore()
        request.app.state.idempotency_store = store
    return store


# Idempotency-Key: opaque, printable-ASCII, bounded (SPEC-API-002 FR-04).
_IDEMPOTENCY_KEY = re.compile(r"^[\x20-\x7e]{8,200}$")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/requests",
    response_model=RequestOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a domain request for async processing",
)
@limiter.limit(f"{settings.rate_limit_requests_per_minute}/minute")
async def submit_request(
    request: Request,
    body: RequestIn,
    response: Response,
    store: RequestStoreProtocol = Depends(get_request_store),
    broker: EventBrokerProtocol = Depends(get_event_broker),
    idempotency: IdempotencyStoreProtocol = Depends(get_idempotency_store),
) -> RequestOut:
    """Accept a request, persist initial state, and publish to the async pipeline.

    Returns 202 Accepted immediately. Poll GET /v1/requests/{id} for the result.
    PII in the request text is masked before the event is published.
    Returns 503 with Retry-After header when all agent slots are occupied.

    An optional ``Idempotency-Key`` header de-duplicates retried submissions (SPEC-API-002):
    a repeated key with the same body replays the original 202; with a different body it is a
    422 ``IDEMPOTENCY_KEY_REUSED``.
    """
    # Idempotency claim (before the capacity gate, so a replay is not blocked by 503).
    idem_key = request.headers.get("Idempotency-Key")
    request_id = str(uuid.uuid4())
    if idem_key is not None:
        if not _IDEMPOTENCY_KEY.match(idem_key):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid Idempotency-Key - printable ASCII, 8-200 chars.",
            )
        content_fp = fingerprint_body(
            mask_dict({"request_text": body.request_text, "priority": body.priority})
        )
        record, created = await idempotency.claim(
            idem_key,
            IdempotencyRecord(
                request_id=request_id, fingerprint=content_fp, created_at=datetime.now(UTC)
            ),
        )
        if not created:
            if record.fingerprint != content_fp:
                raise AppError(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "IDEMPOTENCY_KEY_REUSED",
                    "Idempotency-Key already used with a different request body.",
                )
            prior = await store.get(record.request_id)
            response.headers["Idempotency-Replayed"] = "true"
            logger.info("Idempotent replay", request_id=record.request_id)
            return RequestOut(
                request_id=record.request_id,
                status=prior.status if prior else "queued",
                created_at=prior.created_at if prior else datetime.now(UTC),
                message=f"Idempotent replay. Poll /v1/requests/{record.request_id} for status.",
            )

    sem: Any = getattr(request.app.state, "agent_semaphore", None)
    if sem is not None and sem._value == 0:
        if idem_key is not None:
            await idempotency.release(idem_key)  # roll back the claim so a retry can proceed
        AGENT_SEMAPHORE_WAITING.labels(settings.service_name).inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent capacity exhausted — retry later",
            headers={"Retry-After": "5"},
        )

    now = datetime.now(UTC)

    await store.save(
        RequestState(
            request_id=request_id,
            status="queued",
            created_at=now,
            updated_at=now,
        )
    )

    masked = mask_dict(
        {
            "request_id": request_id,
            "request_text": body.request_text,
            "priority": body.priority,
        }
    )
    envelope = build_envelope("domain.request.created", masked)
    await broker.publish("domain.request.created", envelope, key=request_id)

    logger.info(
        "Request submitted",
        request_id=request_id,
        priority=body.priority,
    )

    return RequestOut(
        request_id=request_id,
        status="queued",
        created_at=now,
        message=f"Request accepted. Poll /v1/requests/{request_id} for status.",
    )


@router.get(
    "/requests/{request_id}",
    response_model=RequestStatusResponse,
    summary="Poll request status",
)
async def get_request_status(
    request_id: str,
    store: RequestStoreProtocol = Depends(get_request_store),
) -> RequestStatusResponse:
    """Return the current processing status of a submitted request.

    Raises 404 if the request_id is not found (unknown or TTL expired).
    """
    state = await store.get(request_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request {request_id} not found.",
        )
    return RequestStatusResponse(
        request_id=state.request_id,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        result=state.result,
        error=state.error,
        message=f"Request is {state.status}.",
    )
