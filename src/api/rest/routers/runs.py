"""Read-only agent-run / execution-trace endpoint.

Flow: GET /v1/runs/{request_id} → load RequestState → build a timeline of audit events
that can be REALLY associated with this request → 200 RunTraceResponse (404 if unknown).

Honesty (CLAUDE.md §3.6): the audit store is not indexed by the domain request_id, and the
orchestrator does not write that id into audit metadata. We therefore associate events only by
the best available *real* signal (an exact ``metadata.request_id`` match) and tell the caller
which strategy produced the timeline via ``timeline_association`` — we never synthesize events
or imply linkage we cannot prove. See specs/api/SPEC-API-004-runs-trace-and-slo-status.md §9.1.

Spec: specs/api/SPEC-API-004-runs-trace-and-slo-status.md
ADR:  ADR-0076 (structured error model), ADR-0011 (human oversight), ADR-0004 (observability)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from src.agents.request_store import RequestState, RequestStoreProtocol
from src.api.rest.auth import Principal, get_principal
from src.api.rest.errors import AppError
from src.api.rest.routers.requests import get_request_store
from src.guardrails.audit_logger import AuditLogger
from src.observability.logger import get_logger

logger = get_logger("api.runs")
router = APIRouter(tags=["runs"])


# ── Dependency ────────────────────────────────────────────────────────────────


def get_audit_logger(request: Request) -> AuditLogger | None:
    """Resolve the AuditLogger from app.state.

    Returns ``None`` rather than raising when no logger is wired: the run trace still
    returns the request state, just with an empty timeline (``timeline_association = none``).
    """
    return getattr(request.app.state, "audit_logger", None)


# ── Schemas ───────────────────────────────────────────────────────────────────


class TraceEvent(BaseModel):
    """One audit event, taken verbatim from the immutable audit trail (no synthesized events)."""

    event_type: str
    action: str
    outcome: str
    risk_score: float | None = None
    trace_id: str | None = None
    occurred_at: datetime


class RunTraceResponse(BaseModel):
    """Per-request execution trace for the operator UI run view (SPEC-API-004)."""

    request_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None
    timeline: list[TraceEvent] = Field(default_factory=list)
    # Which real strategy built `timeline` — so the UI never presents approximate/empty data
    # as if it were an exact request trace (CLAUDE.md §3.6, SPEC-API-004 §9.1).
    timeline_association: str = Field(
        ...,
        description=(
            "metadata_request_id (exact match) | time_window_approximate (reserved, "
            "off by default) | none (no event could be honestly associated)"
        ),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _build_timeline(
    audit: AuditLogger | None,
    state: RequestState,
) -> tuple[list[TraceEvent], str]:
    """Build the timeline from audit events REALLY associable with this request.

    Strategy (SPEC-API-004 §9.1): query the audit trail over the request's lifetime window and
    keep only events whose ``metadata.request_id`` exactly equals the domain request_id. This is
    the sole *exact* signal available today; if none match, return an empty timeline with
    ``none`` rather than guessing.
    """
    if audit is None:
        return [], "none"

    # Lower-bound the query at the request's creation (events cannot precede it); deliberately
    # leave the upper bound open so an exactly-matching event that lands just after updated_at is
    # not dropped by a tight clock window. The exact metadata.request_id match below is the
    # authoritative signal, not the time bound (which only caps the scan). We do NOT filter by
    # agent_id — the domain request is not bound to a single agent_id at this layer.
    events = await audit.query_events(
        from_time=state.created_at,
        limit=500,
    )

    matched = [e for e in events if e.metadata.get("request_id") == state.request_id]
    if not matched:
        return [], "none"

    matched.sort(key=lambda e: e.created_at)
    timeline = [
        TraceEvent(
            event_type=e.event_type,
            action=e.action,
            outcome=e.outcome,
            risk_score=e.risk_score,
            trace_id=e.trace_id,
            occurred_at=e.created_at,
        )
        for e in matched
    ]
    return timeline, "metadata_request_id"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/runs/{request_id}",
    response_model=RunTraceResponse,
    summary="Get a request's execution trace",
)
async def get_run_trace(
    request_id: str,
    _principal: Principal = Depends(get_principal),
    store: RequestStoreProtocol = Depends(get_request_store),
    audit: AuditLogger | None = Depends(get_audit_logger),
) -> RunTraceResponse:
    """Return the execution trace for a single submitted request.

    Requires a valid bearer JWT (read access). Returns the request state plus a ``timeline`` of
    audit events that can be really associated with it (``timeline_association`` names the
    strategy used — see SPEC-API-004 §9.1 for the honest-association limitation).

    Raises 404 (ADR-0076 envelope) if the request_id is unknown or its TTL has expired.
    """
    state = await store.get(request_id)
    if state is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            detail=f"Run {request_id} not found.",
        )

    timeline, association = await _build_timeline(audit, state)

    return RunTraceResponse(
        request_id=state.request_id,
        status=state.status,
        created_at=state.created_at,
        updated_at=state.updated_at,
        result=state.result,
        error=state.error,
        timeline=timeline,
        timeline_association=association,
    )
