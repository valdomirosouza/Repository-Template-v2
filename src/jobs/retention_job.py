"""Data retention job — enforces automated deletion per specs/privacy/data-retention.md.

Spec: specs/privacy/data-retention.md
ADR:  ADR-0013 (Data Retention Policy), ADR-0012 (PII Masking)

Retention schedule enforced here:
  agent_memory_documents  — hard delete after memory_docs_retention_days (default 90)
  audit_events            — archive flag set after 1 year; hard delete after 5 years
                            NOTE: app_user cannot DELETE from audit_events (immutable).
                            The job runs as db_dba_role (see alembic.ini) which retains
                            DELETE privilege. In production this job runs as a dedicated
                            K8s ServiceAccount with its own DB credentials.

Redis TTLs (session cache, HITL store, request store) are enforced at write time — this
job does not touch Redis.

Run via:
  uv run python -m src.jobs.retention_job          # one-shot
  kubectl apply -f infrastructure/k8s/retention-cronjob.yaml   # scheduled
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg

from src.observability.logger import get_logger
from src.shared.config import settings

logger = get_logger("retention_job")


# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class RetentionResult:
    run_at: datetime
    memory_docs_deleted: int
    audit_events_archived: int
    audit_events_hard_deleted: int
    errors: list[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ── Job ───────────────────────────────────────────────────────────────────────


class RetentionJob:
    """Runs data retention sweeps against PostgreSQL.

    Designed to be called once per scheduled run (K8s CronJob or manual).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def run(self) -> RetentionResult:
        run_at = datetime.now(UTC)
        result = RetentionResult(
            run_at=run_at,
            memory_docs_deleted=0,
            audit_events_archived=0,
            audit_events_hard_deleted=0,
            errors=[],
        )

        await self._delete_expired_memory_docs(result)
        await self._archive_old_audit_events(result)
        await self._hard_delete_aged_audit_events(result)
        await self._verify_compliance(result)

        logger.info(
            "Retention job complete",
            run_at=run_at.isoformat(),
            memory_docs_deleted=result.memory_docs_deleted,
            audit_events_archived=result.audit_events_archived,
            audit_events_hard_deleted=result.audit_events_hard_deleted,
            errors=result.errors,
            success=result.success,
        )
        return result

    # ── Memory documents ──────────────────────────────────────────────────────

    async def _delete_expired_memory_docs(self, result: RetentionResult) -> None:
        """Hard-delete agent_memory_documents older than memory_docs_retention_days."""
        cutoff = datetime.now(UTC) - timedelta(days=settings.memory_docs_retention_days)
        try:
            async with self._pool.acquire() as conn:
                deleted = await conn.fetchval(
                    """
                    WITH deleted AS (
                        DELETE FROM agent_memory_documents
                        WHERE created_at < $1
                        RETURNING id
                    )
                    SELECT count(*) FROM deleted
                    """,
                    cutoff,
                )
                result.memory_docs_deleted = int(deleted or 0)
                logger.info(
                    "Memory docs deleted",
                    count=result.memory_docs_deleted,
                    cutoff=cutoff.isoformat(),
                )
        except Exception as exc:
            msg = f"memory_docs deletion failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)

    # ── Audit events — archive ────────────────────────────────────────────────

    async def _archive_old_audit_events(self, result: RetentionResult) -> None:
        """Mark audit_events older than 1 year as archived (cold storage flag).

        Archived records are excluded from active queries but retained for compliance.
        Requires the audit_events table to have an `archived` boolean column added by
        migration 0003_audit_events_archive_column (see docs/adr/ADR-0013).
        """
        archive_cutoff = datetime.now(UTC) - timedelta(days=365)
        try:
            async with self._pool.acquire() as conn:
                # Check if archived column exists before attempting update
                col_exists = await conn.fetchval(
                    """
                    SELECT count(*) FROM information_schema.columns
                    WHERE table_name = 'audit_events' AND column_name = 'archived'
                    """
                )
                if not col_exists:
                    logger.info(
                        "audit_events.archived column not yet present — skipping archive step"
                    )
                    return

                updated = await conn.fetchval(
                    """
                    WITH updated AS (
                        UPDATE audit_events
                        SET archived = TRUE
                        WHERE created_at < $1 AND (archived IS NULL OR archived = FALSE)
                        RETURNING id
                    )
                    SELECT count(*) FROM updated
                    """,
                    archive_cutoff,
                )
                result.audit_events_archived = int(updated or 0)
                logger.info(
                    "Audit events archived",
                    count=result.audit_events_archived,
                    cutoff=archive_cutoff.isoformat(),
                )
        except Exception as exc:
            msg = f"audit_events archive failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)

    # ── Audit events — hard delete ────────────────────────────────────────────

    async def _hard_delete_aged_audit_events(self, result: RetentionResult) -> None:
        """Hard-delete audit_events older than 5 years (regulatory maximum).

        IMPORTANT: This requires the job's DB role to have DELETE on audit_events.
        The application role (app_user) has DELETE revoked (immutability guarantee).
        Run this job as db_dba_role or a dedicated retention role.
        """
        hard_delete_cutoff = datetime.now(UTC) - timedelta(days=5 * 365)
        try:
            async with self._pool.acquire() as conn:
                deleted = await conn.fetchval(
                    """
                    WITH deleted AS (
                        DELETE FROM audit_events
                        WHERE created_at < $1
                        RETURNING id
                    )
                    SELECT count(*) FROM deleted
                    """,
                    hard_delete_cutoff,
                )
                result.audit_events_hard_deleted = int(deleted or 0)
                logger.info(
                    "Audit events hard-deleted",
                    count=result.audit_events_hard_deleted,
                    cutoff=hard_delete_cutoff.isoformat(),
                )
        except Exception as exc:
            # Permission denied is expected if running as app_user — warn, don't fail
            msg = f"audit_events hard-delete failed (check DB role): {exc}"
            logger.warning(msg)
            result.errors.append(msg)

    # ── Compliance verification ───────────────────────────────────────────────

    async def _verify_compliance(self, result: RetentionResult) -> None:
        """Spot-check: confirm no memory docs exceed the retention threshold."""
        cutoff = datetime.now(UTC) - timedelta(days=settings.memory_docs_retention_days)
        try:
            async with self._pool.acquire() as conn:
                overdue = await conn.fetchval(
                    "SELECT count(*) FROM agent_memory_documents WHERE created_at < $1",
                    cutoff,
                )
                overdue_count = int(overdue or 0)
                if overdue_count > 0:
                    msg = (
                        f"COMPLIANCE: {overdue_count} memory docs still exceed retention "
                        f"threshold after deletion sweep"
                    )
                    logger.error(msg)
                    result.errors.append(msg)
                else:
                    logger.info("Compliance check passed — no overdue memory docs")
        except Exception as exc:
            msg = f"compliance verification failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)


# ── Entrypoint ────────────────────────────────────────────────────────────────


async def _main() -> None:
    logging.basicConfig(level=settings.log_level)
    logger.info("Retention job starting", database_url=settings.database_url.split("@")[-1])

    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    try:
        job = RetentionJob(pool)
        result = await job.run()
        if not result.success:
            raise SystemExit(f"Retention job completed with errors: {result.errors}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())
