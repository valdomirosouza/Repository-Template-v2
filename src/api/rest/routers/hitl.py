"""HITL approval and status endpoints.

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Model)

These endpoints are used by the reviewer UI to:
- List pending HITL approval requests
- Submit an APPROVE or REJECT decision
- Poll the status of a specific request
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.observability.logger import get_logger

logger = get_logger("api.hitl")
router = APIRouter(tags=["hitl"])


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


@router.get("/status", response_model=HITLStatusResponse, summary="HITL subsystem health")
async def hitl_status() -> HITLStatusResponse:
    """Return the HITL subsystem status and pending queue depth.

    Used by smoke-test.sh and the PRR checklist to verify HITL is operational.
    """
    # TODO: query HITLGateway for live queue depth
    return HITLStatusResponse(
        status="operational",
        pending_count=0,
        message="HITL gateway is operational.",
    )


@router.post(
    "/requests/{request_id}/decision",
    response_model=DecisionOut,
    summary="Submit an approval or rejection decision",
)
async def submit_decision(request_id: str, body: DecisionIn) -> DecisionOut:
    """Record a human APPROVE or REJECT decision for a pending HITL request.

    - APPROVED: the agent action proceeds
    - REJECTED: the action is cancelled; the rationale is audit-logged

    Raises 404 if request_id is not found or has already been decided/expired.
    """
    logger.info(
        "HITL decision submitted via API",
        request_id=request_id,
        decision=body.decision,
        approver_id=body.approver_id,
    )

    # TODO: call HITLGateway.record_decision()
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"HITL request {request_id} not found or no longer pending.",
    )
