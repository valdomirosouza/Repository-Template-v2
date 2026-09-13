"""Unit tests for src/jobs/retention_job.py (W15-T1, issue #388).

Spec: specs/privacy/data-retention.md · ADR-0013

The job had zero tests. A fake asyncpg pool records every SQL statement and returns scripted
counts, so each sweep, the error isolation per sweep, and the compliance verdict are checked
without PostgreSQL.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from src.jobs.retention_job import RetentionJob, RetentionResult

pytestmark = [pytest.mark.unit, pytest.mark.requirement("SPEC-PRIV-001")]


class _FakeConn:
    def __init__(self, script: dict[str, Any], calls: list[str]) -> None:
        self._script, self._calls = script, calls

    def _key(self, sql: str) -> str:
        s = " ".join(sql.split()).lower()
        if "delete from agent_memory_documents" in s:
            return "memory_delete"
        if "select count(*) from agent_memory_documents" in s:
            return "memory_overdue"
        if "update audit_events" in s or "archived" in s:
            return "audit_archive"
        if "delete from audit_events" in s:
            return "audit_delete"
        return "other"

    async def fetchval(self, sql: str, *args: Any) -> Any:
        key = self._key(sql)
        self._calls.append(key)
        value = self._script.get(key, 0)
        if isinstance(value, Exception):
            raise value
        return value

    async def execute(self, sql: str, *args: Any) -> str:
        key = self._key(sql)
        self._calls.append(key)
        value = self._script.get(key, 0)
        if isinstance(value, Exception):
            raise value
        return f"UPDATE {value}"


class _FakePool:
    def __init__(self, script: dict[str, Any]) -> None:
        self.calls: list[str] = []
        self._script = script

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield _FakeConn(self._script, self.calls)


async def test_run_reports_counts_and_succeeds_when_no_overdue_docs():
    pool = _FakePool(
        {"memory_delete": 7, "audit_archive": 3, "audit_delete": 1, "memory_overdue": 0}
    )
    result = await RetentionJob(pool).run()  # type: ignore[arg-type]
    assert isinstance(result, RetentionResult)
    assert result.memory_docs_deleted == 7
    assert result.errors == [] and result.success
    assert "memory_delete" in pool.calls and "memory_overdue" in pool.calls


async def test_compliance_check_flags_overdue_documents():
    pool = _FakePool({"memory_delete": 0, "memory_overdue": 4})
    result = await RetentionJob(pool).run()  # type: ignore[arg-type]
    assert not result.success
    assert any("COMPLIANCE" in e and "4" in e for e in result.errors)


async def test_a_failing_sweep_is_isolated_and_recorded():
    """One sweep's exception must not abort the others (each is try/except'd)."""
    pool = _FakePool({"memory_delete": RuntimeError("table locked"), "memory_overdue": 0})
    result = await RetentionJob(pool).run()  # type: ignore[arg-type]
    assert result.memory_docs_deleted == 0
    assert any("memory_docs deletion failed" in e and "table locked" in e for e in result.errors)
    assert not result.success
    # the later sweeps still ran
    assert "memory_overdue" in pool.calls


async def test_null_counts_are_treated_as_zero():
    pool = _FakePool({"memory_delete": None, "memory_overdue": None})
    result = await RetentionJob(pool).run()  # type: ignore[arg-type]
    assert result.memory_docs_deleted == 0
    assert result.success


def test_result_success_is_derived_from_errors():
    from datetime import UTC, datetime

    ok = RetentionResult(datetime.now(UTC), 0, 0, 0, [])
    bad = RetentionResult(datetime.now(UTC), 0, 0, 0, ["x"])
    assert ok.success and not bad.success
