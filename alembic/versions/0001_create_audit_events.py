"""Create audit_events table.

Revision ID: 0001
Revises:
Create Date: 2026-05-24

Spec: specs/ai/guardrails.md (Layer 4 — Audit Logger)
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)

The table is INSERT-only: UPDATE and DELETE privileges are revoked from the
application role so the audit log is immutable even at the SQL level.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("agent_id", sa.Text, nullable=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("outcome", sa.Text, nullable=False),
        sa.Column("risk_score", sa.Float, nullable=True),
        sa.Column("metadata", sa.Text, nullable=True),
        sa.Column("trace_id", sa.Text, nullable=True),
        sa.Column("approver_id", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_audit_events_agent_created",
        "audit_events",
        ["agent_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_type_created",
        "audit_events",
        ["event_type", "created_at"],
    )

    # Revoke mutable operations from the application role to make the audit log immutable
    # at the SQL level. The role name is read from alembic.ini (db_app_role key) so that
    # adopters only need to change it in one place. A DO $$ guard emits a WARNING (not an
    # error) when the role doesn't exist, preventing silent failure on fresh environments.
    role = context.config.get_main_option("db_app_role", "app_user")
    # role comes from alembic.ini (a config file, not user input).
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
            REVOKE UPDATE, DELETE ON audit_events FROM {role};
          ELSE
            RAISE WARNING
              'DB role {role} not found — audit_events REVOKE skipped.'
              ' Set db_app_role in alembic.ini.';
          END IF;
        END
        $$"""
    )


def downgrade() -> None:
    role = context.config.get_main_option("db_app_role", "app_user")
    op.execute(f"GRANT UPDATE, DELETE ON audit_events TO {role}")
    op.drop_index("ix_audit_events_type_created", table_name="audit_events")
    op.drop_index("ix_audit_events_agent_created", table_name="audit_events")
    op.drop_table("audit_events")
