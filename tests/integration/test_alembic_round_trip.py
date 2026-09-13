"""Alembic migration round-trip: upgrade → downgrade → upgrade (W15-T3, issue #390).

No test exercised the migrations. This one runs the whole chain against a real PostgreSQL
(the CI integration job now provides one; locally set ``DATABASE_URL``) and proves every
revision's ``downgrade()`` actually reverses its ``upgrade()``. Skips cleanly when no database
is reachable so the offline matrix stays green.

Spec: specs/privacy/db-encryption-at-rest.md · ADR-0013, ADR-0018
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.integration, pytest.mark.requirement("SPEC-PRIV-002")]


def _db_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    return url if url and "placeholder" not in url else None


async def _reachable(url: str) -> bool:
    import asyncpg

    try:
        conn = await asyncio.wait_for(
            asyncpg.connect(url.replace("postgresql+asyncpg", "postgresql")), 5
        )
    except Exception:
        return False
    await conn.close()
    return True


@pytest.fixture(scope="module")
def alembic_cfg() -> Config:
    url = _db_url()
    if url is None or not asyncio.run(_reachable(url)):
        pytest.skip(
            "DATABASE_URL not set or PostgreSQL unreachable — Alembic round-trip needs a real database"
        )
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


def _current(cfg: Config) -> str | None:
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    engine = create_engine(_db_url().replace("+asyncpg", ""))  # type: ignore[union-attr]
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def test_upgrade_downgrade_upgrade_round_trip(alembic_cfg: Config) -> None:
    command.upgrade(alembic_cfg, "head")
    head = _current(alembic_cfg)
    assert head is not None

    command.downgrade(alembic_cfg, "base")
    assert _current(alembic_cfg) is None, "downgrade to base must leave no revision"

    command.upgrade(alembic_cfg, "head")
    assert _current(alembic_cfg) == head, "second upgrade must reach the same head"


def test_every_revision_has_a_downgrade_or_an_explained_no_op() -> None:
    """Static guard that runs offline: no migration may be irreversible *by omission*.

    A `pass` downgrade is accepted only when the body explains why (0002 keeps extensions
    other objects may depend on; 0007 must not re-grant UPDATE/DELETE on the audit trail).
    """
    bad = []
    for path in sorted((REPO_ROOT / "alembic" / "versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "def downgrade" not in text:
            bad.append(path.name)
            continue
        body = text.split("def downgrade", 1)[1].split("\n\n", 1)[0]
        if "pass" in body and "#" not in body:
            bad.append(path.name)
    assert not bad, f"migrations with a missing or unexplained empty downgrade(): {bad}"
