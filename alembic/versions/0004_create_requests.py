"""Create requests table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27

Spec: specs/system/async-event-flow.md, specs/system/architecture.md
ADR:  ADR-0003 (Async API Strategy)

Stores the lifecycle of every domain request from submission through completion.
The table is the durable fallback when Redis TTL evicts in-flight request state.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default="queued",
            comment="queued | processing | completed | failed",
        ),
        sa.Column(
            "priority",
            sa.Text,
            nullable=False,
            server_default="normal",
            comment="low | normal | high",
        ),
        # PII-masked JSON payload — raw user input is never stored.
        sa.Column("masked_payload", sa.Text, nullable=True),
        # JSON of the processing result produced by the agent orchestrator.
        sa.Column("result", sa.Text, nullable=True),
        # Non-null when the request was rejected or an error occurred.
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_index("ix_requests_status_created", "requests", ["status", "created_at"])
    op.create_index("ix_requests_created", "requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_requests_created", table_name="requests")
    op.drop_index("ix_requests_status_created", table_name="requests")
    op.drop_table("requests")
