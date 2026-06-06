"""Add agent_context_graphs table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-05

Spec: specs/ai/context-graph.md
ADR:  ADR-0041 (Context Graph — Autonomy Tier)

Stores serialised ContextGraph instances as JSONB for durable goal-state
persistence across agent sessions. Required for Gartner Autonomy (Level 4).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_context_graphs",
        sa.Column("graph_id", sa.Text, primary_key=True),
        # NB: no index=True here — the session_id index is created explicitly below
        # (and dropped by downgrade). Declaring both produced a duplicate
        # ix_agent_context_graphs_session_id and failed the migration on any fresh DB.
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("root_goal_description", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column(
            "graph_data",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            comment="Full ContextGraph serialisation (specs/ai/context-graph.md)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_agent_context_graphs_session_id",
        "agent_context_graphs",
        ["session_id"],
    )
    op.create_index(
        "ix_agent_context_graphs_status",
        "agent_context_graphs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_context_graphs_status", table_name="agent_context_graphs")
    op.drop_index("ix_agent_context_graphs_session_id", table_name="agent_context_graphs")
    op.drop_table("agent_context_graphs")
