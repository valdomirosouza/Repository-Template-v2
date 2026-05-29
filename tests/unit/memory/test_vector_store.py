"""Unit tests for src/memory/vector_store.py.

Spec: specs/ai/agent-memory.md §3.1
ADR:  ADR-0017 (Agent Memory Architecture)

All tests use InMemoryVectorStore and StubEmbedder — no external services needed.
"""

from __future__ import annotations

import math

import pytest

from src.memory.vector_store import (
    InMemoryVectorStore,
    StubEmbedder,
    VectorDocument,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_doc(content: str = "test content", source: str = "spec") -> VectorDocument:
    return VectorDocument(
        content=content,
        embedding=[0.1] * 256,
        source=source,
        tags=[source],
    )


# ── StubEmbedder ──────────────────────────────────────────────────────────────


class TestStubEmbedder:
    @pytest.mark.asyncio
    async def test_returns_vector_of_correct_dim(self) -> None:
        embedder = StubEmbedder(dim=64)
        vec = await embedder.embed("hello")
        assert len(vec) == 64

    @pytest.mark.asyncio
    async def test_same_input_same_output(self) -> None:
        embedder = StubEmbedder()
        a = await embedder.embed("spec text")
        b = await embedder.embed("spec text")
        assert a == b

    @pytest.mark.asyncio
    async def test_different_inputs_different_outputs(self) -> None:
        embedder = StubEmbedder()
        a = await embedder.embed("spec content about agents")
        b = await embedder.embed("adr content about databases")
        assert a != b

    @pytest.mark.asyncio
    async def test_output_is_unit_normalised(self) -> None:
        embedder = StubEmbedder(dim=32)
        vec = await embedder.embed("normalised test")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_handles_empty_string(self) -> None:
        embedder = StubEmbedder(dim=16)
        vec = await embedder.embed("")
        assert len(vec) == 16


# ── InMemoryVectorStore.upsert ────────────────────────────────────────────────


class TestInMemoryVectorStoreUpsert:
    @pytest.mark.asyncio
    async def test_returns_doc_id(self) -> None:
        store = InMemoryVectorStore()
        doc = _make_doc()
        result = await store.upsert(doc)
        assert result == doc.id

    @pytest.mark.asyncio
    async def test_document_retrievable_after_upsert(self) -> None:
        store = InMemoryVectorStore()
        doc = _make_doc("unique content")
        await store.upsert(doc)
        results = await store.search(doc.embedding, k=1)
        assert len(results) == 1
        assert results[0].id == doc.id

    @pytest.mark.asyncio
    async def test_upsert_overwrites_existing_doc(self) -> None:
        store = InMemoryVectorStore()
        doc = _make_doc("original")
        await store.upsert(doc)

        updated = VectorDocument(
            id=doc.id,
            content="updated",
            embedding=doc.embedding,
            source="adr",
        )
        await store.upsert(updated)

        results = await store.search(doc.embedding, k=1)
        assert results[0].content == "updated"

    @pytest.mark.asyncio
    async def test_multiple_docs_stored(self) -> None:
        store = InMemoryVectorStore()
        for i in range(5):
            await store.upsert(_make_doc(f"doc {i}"))
        results = await store.search([0.1] * 256, k=10)
        assert len(results) == 5


# ── InMemoryVectorStore.search ────────────────────────────────────────────────


class TestInMemoryVectorStoreSearch:
    @pytest.mark.asyncio
    async def test_returns_empty_when_store_is_empty(self) -> None:
        store = InMemoryVectorStore()
        results = await store.search([0.5] * 256, k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_at_most_k_results(self) -> None:
        store = InMemoryVectorStore()
        for i in range(10):
            await store.upsert(_make_doc(f"doc {i}"))
        results = await store.search([0.1] * 256, k=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_most_similar_doc_ranked_first(self) -> None:
        store = InMemoryVectorStore()
        # Doc A has a strong match in dim 0
        doc_a = VectorDocument(content="A", embedding=[1.0] + [0.0] * 255, source="spec")
        # Doc B has a strong match in dim 1
        doc_b = VectorDocument(content="B", embedding=[0.0, 1.0] + [0.0] * 254, source="spec")
        await store.upsert(doc_a)
        await store.upsert(doc_b)

        # Query pointing toward dim 0
        query = [1.0] + [0.0] * 255
        results = await store.search(query, k=2)
        assert results[0].content == "A"

    @pytest.mark.asyncio
    async def test_source_filter_excludes_other_sources(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(_make_doc("spec doc", source="spec"))
        await store.upsert(_make_doc("adr doc", source="adr"))

        results = await store.search([0.1] * 256, k=5, source_filter="spec")
        assert all(d.source == "spec" for d in results)

    @pytest.mark.asyncio
    async def test_source_filter_returns_empty_when_no_match(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(_make_doc(source="adr"))

        results = await store.search([0.1] * 256, k=5, source_filter="hitl_rejection")
        assert results == []


# ── InMemoryVectorStore.delete ────────────────────────────────────────────────


class TestInMemoryVectorStoreDelete:
    @pytest.mark.asyncio
    async def test_deleted_doc_not_returned_in_search(self) -> None:
        store = InMemoryVectorStore()
        doc = _make_doc()
        await store.upsert(doc)
        await store.delete(doc.id)

        results = await store.search(doc.embedding, k=5)
        assert all(d.id != doc.id for d in results)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_doc_does_not_raise(self) -> None:
        store = InMemoryVectorStore()
        await store.delete("nonexistent-id")  # must not raise


# ── cosine similarity edge cases ──────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self) -> None:
        v = [0.5] * 4
        score = InMemoryVectorStore._cosine_similarity(v, v)
        assert abs(score - 1.0) < 1e-9

    def test_orthogonal_vectors_score_zero(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        score = InMemoryVectorStore._cosine_similarity(a, b)
        assert abs(score) < 1e-9

    def test_mismatched_lengths_return_zero(self) -> None:
        score = InMemoryVectorStore._cosine_similarity([1.0, 2.0], [1.0])
        assert score == 0.0

    def test_empty_vectors_return_zero(self) -> None:
        score = InMemoryVectorStore._cosine_similarity([], [])
        assert score == 0.0
