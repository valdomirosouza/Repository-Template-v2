"""Immutable audit logger for all agent decisions and actions.

Write-before-execute invariant: callers must call log_event() and await its
completion before dispatching any action. A raised AuditWriteError must be
treated as a hard failure — the action must not proceed.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Protocol

from src.observability.logger import get_logger
from src.shared.models import AuditEvent

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
        self._records.append(event)

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
    """PostgreSQL append-only audit storage stub. Implement with asyncpg or SQLAlchemy."""

    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    async def append(self, event: AuditEvent) -> None:
        # INSERT INTO audit_events (...) VALUES (...) — no UPDATE, no DELETE
        raise NotImplementedError("PostgresAuditStorage.append() not yet implemented")

    async def query(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        raise NotImplementedError("PostgresAuditStorage.query() not yet implemented")


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
