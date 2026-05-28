"""Create agent_memory_documents table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-28

Spec: specs/ai/agent-memory.md §3.1
ADR:  ADR-0017 (Agent Memory Architecture), ADR-0018 (Database Encryption at Rest)

The `content` column stores AES-256-GCM encrypted text (enc:v1:... wire format).
Encryption and decryption are applied at the application layer by
src/shared/db_encryption.py — the column schema is plain TEXT.

The `embedding` column stores vectors via the pgvector `vector` type (enabled in
migration 0002). The EMBEDDING_DIM constant must match settings.memory_embedding_dim.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Must match settings.memory_embedding_dim (default 256).
# Change here AND in settings before running this migration if a different
# embedding model is used.
EMBEDDING_DIM = 256


def upgrade() -> None:
    op.create_table(
        "agent_memory_documents",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),  # AES-256-GCM encrypted
        sa.Column(
            "embedding",
            sa.Text,  # stored as vector literal "[x,y,...]"; cast by pgvector
            nullable=False,
        ),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("tags", sa.ARRAY(sa.Text), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Change the embedding column type to the pgvector `vector` type after table
    # creation — SQLAlchemy core does not have a built-in Vector type.
    op.execute(
        f"ALTER TABLE agent_memory_documents "
        f"ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM}) "
        f"USING embedding::vector({EMBEDDING_DIM})"
    )

    op.create_index(
        "ix_agent_memory_source_created",
        "agent_memory_documents",
        ["source", "created_at"],
    )

    # IVFFlat index for approximate nearest-neighbour search.
    # lists=100 is a reasonable starting value for up to ~1 M rows.
    op.execute(
        "CREATE INDEX ix_agent_memory_embedding_ivfflat "
        "ON agent_memory_documents "
        "USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_index("ix_agent_memory_embedding_ivfflat", table_name="agent_memory_documents")
    op.drop_index("ix_agent_memory_source_created", table_name="agent_memory_documents")
    op.drop_table("agent_memory_documents")
