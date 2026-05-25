"""Base domain models shared across all services.

Spec: specs/system/architecture.md (Component Overview)
ADR:  ADR-0002 (Technology Stack Selection)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class BaseModel(PydanticBaseModel):
    """Base for all domain models. Provides id, created_at, updated_at."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class AgentActionRequest(BaseModel):
    """A request for an agent to perform an action, pending safety evaluation."""

    agent_id: str
    action_type: str
    parameters: dict[str, Any]
    risk_score: float = Field(ge=0.0, le=1.0)
    requires_hitl: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class AgentActionResult(BaseModel):
    """The outcome of an agent action after all safety gates have been applied."""

    request_id: UUID
    agent_id: str
    action_type: str
    status: str  # completed | rejected | failed | pending_hitl
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    hitl_decision: str | None = None


class AuditEvent(BaseModel):
    """Immutable audit record for every agent decision and action."""

    event_type: str
    agent_id: str | None = None
    user_id: str | None = None  # anonymised internal ID only — not L1/L2 PII
    action: str
    outcome: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    approver_id: str | None = None
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
