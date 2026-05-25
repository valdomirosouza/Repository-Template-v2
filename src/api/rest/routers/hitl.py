"""HITL approval and status endpoints.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Model)

These endpoints are used by the reviewer UI to:
- List pending HITL approval requests
- Submit an APPROVE or REJECT decision
- Poll the status of a specific request
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.agents.hitl_gateway import (
    HITLDecision,
    HITLGateway,
    HITLGatewayError,
    HITLStatus,
)
from src.observability.logger import get_logger

logger = get_logger("api.hitl")
router = APIRouter(tags=["hitl"])


# ── Dependency ────────────────────────────────────────────────────────────────


def get_hitl_gateway(request: Request) -> HITLGateway:
    """FastAPI dependency: resolves the HITLGateway from app.state."""
    gateway: HITLGateway | None = getattr(request.app.state, "hitl_gateway", None)
    if gateway is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HITL gateway not initialised",
        )
    return gateway


# ── Schemas ───────────────────────────────────────────────────────────────────


class HITLStatusResponse(BaseModel):
    status: str
    pending_count: int
    message: str


class DecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    rationale: str = Field(..., min_length=10, max_length=1000)
    approver_id: str = Field(..., min_length=1)


class DecisionOut(BaseModel):
    request_id: str
    decision: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/status", response_model=HITLStatusResponse, summary="HITL subsystem health")
async def hitl_status(
    gateway: HITLGateway = Depends(get_hitl_gateway),
) -> HITLStatusResponse:
    """Return the HITL subsystem status and pending queue depth."""
    async with gateway._lock:
        pending = sum(1 for r in gateway._requests.values() if r.status == HITLStatus.PENDING)
    return HITLStatusResponse(
        status="operational",
        pending_count=pending,
        message="HITL gateway is operational.",
    )


@router.post(
    "/requests/{request_id}/decision",
    response_model=DecisionOut,
    summary="Submit an approval or rejection decision",
)
async def submit_decision(
    request_id: str,
    body: DecisionIn,
    gateway: HITLGateway = Depends(get_hitl_gateway),
) -> DecisionOut:
    """Record a human APPROVE or REJECT decision for a pending HITL request.

    - APPROVED: the agent action proceeds
    - REJECTED: the action is cancelled; the rationale is audit-logged

    Raises 404 if request_id is not found, already decided, or expired.
    """
    logger.info(
        "HITL decision submitted via API",
        request_id=request_id,
        decision=body.decision,
        approver_id=body.approver_id,
    )

    decision = HITLDecision(
        request_id=request_id,
        decision=HITLStatus(body.decision),
        approver_id=body.approver_id,
        rationale=body.rationale,
        decided_at=datetime.now(UTC),
    )

    try:
        await gateway.record_decision(decision)
    except HITLGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DecisionOut(
        request_id=request_id,
        decision=body.decision,
        message=f"Decision {body.decision} recorded for request {request_id}.",
    )
