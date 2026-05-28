"""Enable pgcrypto and vector extensions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28

Spec: specs/privacy/db-encryption-at-rest.md
ADR:  ADR-0018 (Database Encryption at Rest), ADR-0017 (Agent Memory Architecture)

pgcrypto — provides gen_random_uuid(), digest(), and cryptographic primitives
           available for future DB-side use (e.g., integrity checks in migrations).
           Application-layer encryption (src/shared/db_encryption.py) does NOT rely
           on pgcrypto; this extension is enabled for operational utility.

vector   — required by PostgresVectorStore (ADR-0017) for pgvector similarity search
           on agent_memory_documents.embedding.
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Extensions are intentionally not dropped: other tables or functions may
    # depend on them, and dropping them could cascade unexpectedly.
    pass
