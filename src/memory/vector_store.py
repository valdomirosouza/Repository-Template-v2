"""VectorStore — semantic similarity search for agent memory.

Spec: specs/ai/agent-memory.md §3.1
ADR:  ADR-0017 (Agent Memory Architecture), ADR-0018 (Database Encryption at Rest)
DPIA: docs/privacy/dpia/dpia-agent-memory.md

PRIVACY INVARIANT: content passed to upsert() MUST be pii_filter-masked by the
caller. The VectorStore does not apply masking itself — the enforcement point is
the call site (DocumentIndexer, BugHistoryStore).

Two implementations:
  InMemoryVectorStore  — cosine similarity; no external deps; for tests and local dev
  PostgresVectorStore  — pgvector extension; production use only
                         Accepts an optional EncryptedField for AES-256-GCM at-rest
                         encryption of the content column (ADR-0018).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.observability.logger import get_logger

if TYPE_CHECKING:
    import asyncpg

    from src.shared.db_encryption import EncryptedField

logger = get_logger("memory.vector_store")

EMBEDDING_DIM_DEFAULT = 256


@dataclass
class VectorDocument:
    """A single document stored in the vector store.

    Spec: specs/ai/agent-memory.md §3.1
    Invariant: content must be PII-masked before this object is created.
    """

    content: str
    embedding: list[float]
    source: str  # "spec" | "adr" | "hitl_rejection" | "sprint_outcome"
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class VectorStore(Protocol):
    """Append-and-search store for document embeddings.

    Spec: specs/ai/agent-memory.md §3.1
    """

    async def upsert(self, doc: VectorDocument) -> str:
        """Store or update a document. Returns the document ID."""
        ...

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        source_filter: str | None = None,
    ) -> list[VectorDocument]:
        """Return the k most similar documents, optionally filtered by source."""
        ...

    async def delete(self, doc_id: str) -> None:
        """Remove a document by ID."""
        ...


@runtime_checkable
class Embedder(Protocol):
    """Converts text to a float embedding vector.

    Production implementations inject a real model; StubEmbedder is used in tests.
    Text passed to embed() must be PII-masked by the caller.
    """

    async def embed(self, text: str) -> list[float]: ...


class StubEmbedder:
    """Deterministic stub embedder for unit tests.

    Returns a fixed-length vector where each component is derived from the
    character ordinals of the text — consistent across calls for the same input.
    """

    def __init__(self, dim: int = EMBEDDING_DIM_DEFAULT) -> None:
        self._dim = dim

    async def embed(self, text: str) -> list[float]:
        base = [float(ord(c)) for c in (text or " ")]
        result: list[float] = []
        for i in range(self._dim):
            result.append(base[i % len(base)] / 128.0)
        norm = math.sqrt(sum(x * x for x in result)) or 1.0
        return [x / norm for x in result]


class InMemoryVectorStore:
    """In-memory vector store using cosine similarity. Not for production use.

    Spec: specs/ai/agent-memory.md §3.1
    """

    def __init__(self) -> None:
        self._docs: dict[str, VectorDocument] = {}

    async def upsert(self, doc: VectorDocument) -> str:
        self._docs[doc.id] = doc
        logger.info("Vector doc upserted", doc_id=doc.id, source=doc.source)
        return doc.id

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        source_filter: str | None = None,
    ) -> list[VectorDocument]:
        candidates = list(self._docs.values())
        if source_filter:
            candidates = [d for d in candidates if d.source == source_filter]

        scored = [(self._cosine_similarity(query_embedding, d.embedding), d) for d in candidates]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [doc for _, doc in scored[:k]]

    async def delete(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (norm_a * norm_b)


class PostgresVectorStore:
    """Production vector store backed by PostgreSQL + pgvector.

    Requires migration 0002 (pgcrypto + vector extensions) and migration 0003
    (agent_memory_documents table).

    Spec: specs/ai/agent-memory.md §3.1
    ADR:  ADR-0017, ADR-0018 (Database Encryption at Rest)

    Pass an EncryptedField instance to enable AES-256-GCM at-rest encryption
    of the content column. When encryption is None the store operates without
    encryption — only valid for local dev (blocked in app_env=production by
    Settings.reject_placeholder_secrets).
    """

    _UPSERT = """
        INSERT INTO agent_memory_documents
            (id, content, embedding, source, tags, created_at)
        VALUES ($1, $2, $3::vector, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE
            SET content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                tags = EXCLUDED.tags
    """

    # Two separate parameterised queries — source_filter is $3 when present.
    # Never interpolate source_filter into the SQL string (SQL injection risk).
    _SEARCH_ALL = """
        SELECT id, content, embedding::text, source, tags, created_at
        FROM agent_memory_documents
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """

    _SEARCH_FILTERED = """
        SELECT id, content, embedding::text, source, tags, created_at
        FROM agent_memory_documents
        WHERE source = $3
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """

    _DELETE = "DELETE FROM agent_memory_documents WHERE id = $1"

    def __init__(
        self,
        pool: asyncpg.Pool,
        encryption: EncryptedField | None = None,
    ) -> None:
        self._pool = pool
        self._encryption = encryption

    async def upsert(self, doc: VectorDocument) -> str:
        content = self._encryption.encrypt(doc.content) if self._encryption else doc.content
        embedding_str = f"[{','.join(str(x) for x in doc.embedding)}]"
        async with self._pool.acquire() as conn:
            await conn.execute(
                self._UPSERT,
                doc.id,
                content,
                embedding_str,
                doc.source,
                doc.tags,
                doc.created_at,
            )
        logger.debug("Vector doc upserted (postgres)", doc_id=doc.id, source=doc.source)
        return doc.id

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        source_filter: str | None = None,
    ) -> list[VectorDocument]:
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        async with self._pool.acquire() as conn:
            if source_filter is not None:
                rows = await conn.fetch(self._SEARCH_FILTERED, embedding_str, k, source_filter)
            else:
                rows = await conn.fetch(self._SEARCH_ALL, embedding_str, k)

        return [
            VectorDocument(
                id=row["id"],
                content=(
                    self._encryption.decrypt(row["content"]) if self._encryption else row["content"]
                ),
                embedding=self._parse_vector(row["embedding"]),
                source=row["source"],
                tags=list(row["tags"] or []),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def delete(self, doc_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(self._DELETE, doc_id)

    @staticmethod
    def _parse_vector(raw: str) -> list[float]:
        return [float(x) for x in raw.strip("[]").split(",")]
