"""Domain request submission and status endpoints.

Spec: specs/system/architecture.md, specs/system/async-event-flow.md
ADR:  ADR-0002 (Technology Stack), ADR-0003 (Async API Strategy)

Flow: POST /v1/requests → validate → publish domain.request.created → return 202
      GET  /v1/requests/{id} → return current status (polling model)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.guardrails.pii_filter import mask_dict
from src.observability.logger import get_logger

logger = get_logger("api.requests")
router = APIRouter(tags=["requests"])


class RequestIn(BaseModel):
    request_text: str = Field(..., min_length=1, max_length=4000)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")


class RequestOut(BaseModel):
    request_id: str
    status: str
    created_at: datetime
    message: str


@router.post(
    "/requests",
    response_model=RequestOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a domain request for async processing",
)
async def submit_request(body: RequestIn) -> RequestOut:
    """Accept a request and publish it to the async processing pipeline.

    Returns 202 Accepted immediately. Poll GET /v1/requests/{id} for the result.
    PII in the request text is masked before the event is published to Kafka.
    """
    request_id = str(uuid.uuid4())

    masked_payload = mask_dict({"request_text": body.request_text, "priority": body.priority})
    logger.info(
        "Request submitted",
        request_id=request_id,
        priority=body.priority,
        # masked_payload logged, not raw body
        payload_preview=str(masked_payload)[:100],
    )

    # TODO: publish domain.request.created to Kafka via async producer
    # await broker.publish("domain.request.created", envelope(masked_payload, request_id))

    return RequestOut(
        request_id=request_id,
        status="queued",
        created_at=datetime.now(timezone.utc),
        message="Request accepted. Poll /v1/requests/{request_id} for status.",
    )


@router.get(
    "/requests/{request_id}",
    response_model=RequestOut,
    summary="Poll request status",
)
async def get_request_status(request_id: str) -> RequestOut:
    """Return the current processing status of a submitted request.

    Raises 404 if the request_id is not found.
    """
    # TODO: query request state store (Redis or DB)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Request {request_id} not found.",
    )
