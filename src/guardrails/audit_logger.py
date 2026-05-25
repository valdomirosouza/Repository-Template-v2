"""Immutable audit logger for all agent decisions and actions.

Write-before-execute invariant: callers must call log_event() and await its
completion before dispatching any action. A raised AuditWriteError must be
treated as a hard failure — the action must not proceed.

Spec: specs/ai/guardrails.md (Layer 4 — Audit Logger)
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from src.observability.logger import get_logger
from src.shared.models import AuditEvent

if TYPE_CHECKING:
    import asyncpg

    from src.shared.db_client import ResilientDBPool

logger = get_logger("audit_logger")


class AuditWriteError(Exception):
    """Raised when the audit log write fails. The associated action must be blocked."""


class AuditStorage(Protocol):
    """Append-only storage backend for audit events."""

    async def append(self, event: AuditEvent) -> None: ...

    async def query(
        self,
        agent_id: str | None,
        action_type: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
        limit: int,
    ) -> list[AuditEvent]: ...


class InMemoryAuditStorage:
    """In-memory storage for testing. Not suitable for production."""

    def __init__(self) -> None:
        self._records: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self._records.append(event.model_copy())

    async def query(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        results = self._records
        if agent_id:
            results = [e for e in results if e.agent_id == agent_id]
        if action_type:
            results = [e for e in results if e.action == action_type]
        if from_time:
            results = [e for e in results if e.created_at >= from_time]
        if to_time:
            results = [e for e in results if e.created_at <= to_time]
        return results[-limit:]


class PostgresAuditStorage:
    """PostgreSQL append-only audit storage backed by asyncpg.

    The audit_events table is INSERT-only: UPDATE and DELETE are revoked from
    the application role in the Alembic migration so the audit log is immutable
    even against application-level bugs.

    Schema: alembic/versions/0001_create_audit_events.py
    """

    _INSERT = """
        INSERT INTO audit_events (
            id, event_type, agent_id, user_id, action, outcome,
            risk_score, metadata, trace_id, approver_id, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    """

    _SELECT_BASE = """
        SELECT id, event_type, agent_id, user_id, action, outcome,
               risk_score, metadata, trace_id, approver_id, created_at
        FROM audit_events
    """

    def __init__(self, pool: asyncpg.Pool | ResilientDBPool) -> None:
        self._pool = pool

    async def append(self, event: AuditEvent) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                self._INSERT,
                str(event.id),
                event.event_type,
                event.agent_id,
                event.user_id,
                event.action,
                event.outcome,
                event.risk_score,
                json.dumps(event.metadata),
                event.trace_id,
                event.approver_id,
                event.created_at,
            )

    async def query(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        conditions: list[str] = []
        params: list[object] = []
        idx = 1

        if agent_id is not None:
            conditions.append(f"agent_id = ${idx}")
            params.append(agent_id)
            idx += 1
        if action_type is not None:
            conditions.append(f"action = ${idx}")
            params.append(action_type)
            idx += 1
        if from_time is not None:
            conditions.append(f"created_at >= ${idx}")
            params.append(from_time)
            idx += 1
        if to_time is not None:
            conditions.append(f"created_at <= ${idx}")
            params.append(to_time)
            idx += 1

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        order_limit = f" ORDER BY created_at DESC LIMIT ${idx}"
        params.append(limit)

        sql = self._SELECT_BASE + where + order_limit

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [
            AuditEvent(
                id=row["id"],
                event_type=row["event_type"],
                agent_id=row["agent_id"],
                user_id=row["user_id"],
                action=row["action"],
                outcome=row["outcome"],
                risk_score=row["risk_score"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                trace_id=row["trace_id"],
                approver_id=row["approver_id"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


class AuditLogger:
    """Writes immutable audit records for all agent actions.

    Must be instantiated with a storage backend and injected into all
    components that execute agent actions (hitl_gateway, agent_loop).
    """

    def __init__(self, storage_backend: AuditStorage) -> None:
        self._storage = storage_backend

    async def log_event(self, event: AuditEvent) -> str:
        """Append an audit event. Returns the event ID on success.

        Raises AuditWriteError if the write fails. Callers must block the
        associated action when this error is raised — never swallow it.
        """
        if not event.id:
            object.__setattr__(event, "id", uuid.uuid4())

        try:
            await self._storage.append(event)
            logger.audit(
                "audit_event_written",
                event_id=str(event.id),
                event_type=event.event_type,
                agent_id=event.agent_id,
                action=event.action,
                outcome=event.outcome,
                trace_id=event.trace_id,
            )
            return str(event.id)

        except Exception as exc:
            logger.error(
                "Audit write failed — action must be blocked",
                event_type=event.event_type,
                agent_id=event.agent_id,
                error=str(exc),
            )
            raise AuditWriteError(
                f"Audit write failed for event {event.event_type}: {exc}"
            ) from exc

    async def query_events(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        return await self._storage.query(
            agent_id=agent_id,
            action_type=action_type,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )
