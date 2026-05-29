"""Create hitl_requests_archive table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-27

Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)

Provides durable storage for HITL request history beyond the Redis TTL.
Redis is the operational store (fast, low-latency access for the gateway).
This table is the long-term audit and compliance record.

Inserts happen when the HITLGateway archives a decided or expired request.
The table is append-only for the application role — UPDATE/DELETE are revoked.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hitl_requests_archive",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column(
            "action_type",
            sa.Text,
            nullable=False,
            comment="Identifies the class of action that required human review",
        ),
        # JSON of PII-masked action parameters shown to the reviewer.
        sa.Column("action_parameters", sa.Text, nullable=True),
        sa.Column("risk_score", sa.Float, nullable=False),
        # Short PII-masked summary surfaced in the reviewer UI.
        sa.Column("context_summary", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            comment="APPROVED | REJECTED | EXPIRED",
        ),
        sa.Column("approver_id", sa.Text, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_hitl_archive_agent_created",
        "hitl_requests_archive",
        ["agent_id", "created_at"],
    )
    op.create_index(
        "ix_hitl_archive_status_created",
        "hitl_requests_archive",
        ["status", "created_at"],
    )

    role = context.config.get_main_option("db_app_role", "app_user")
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
            REVOKE UPDATE, DELETE ON hitl_requests_archive FROM {role};
          ELSE
            RAISE WARNING
              'DB role {role} not found — hitl_requests_archive REVOKE skipped.'
              ' Set db_app_role in alembic.ini.';
          END IF;
        END
        $$"""
    )


def downgrade() -> None:
    role = context.config.get_main_option("db_app_role", "app_user")
    op.execute(f"GRANT UPDATE, DELETE ON hitl_requests_archive TO {role}")
    op.drop_index("ix_hitl_archive_status_created", table_name="hitl_requests_archive")
    op.drop_index("ix_hitl_archive_agent_created", table_name="hitl_requests_archive")
    op.drop_table("hitl_requests_archive")
