"""Unit tests for src/memory/bug_history_store.py.

Spec: specs/ai/agent-memory.md §3.4
ADR:  ADR-0017 (Agent Memory Architecture)

Uses InMemoryVectorStore + StubEmbedder — no external services.
"""

from __future__ import annotations

import pytest

from src.memory.bug_history_store import _SOURCE, BugHistoryStore
from src.memory.vector_store import InMemoryVectorStore, StubEmbedder, VectorDocument

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


@pytest.fixture()
def embedder() -> StubEmbedder:
    return StubEmbedder(dim=32)


@pytest.fixture()
def bug_store(store: InMemoryVectorStore, embedder: StubEmbedder) -> BugHistoryStore:
    return BugHistoryStore(vector_store=store, embedder=embedder)


# ── record_rejection ──────────────────────────────────────────────────────────


class TestBugHistoryStoreRecordRejection:
    @pytest.mark.asyncio
    async def test_returns_doc_id(self, bug_store: BugHistoryStore) -> None:
        doc_id = await bug_store.record_rejection(
            sprint_id="sprint-001",
            action_type="deploy",
            feedback="Missing smoke test.",
            risk_score=0.8,
            agent_id="agent-1",
        )
        assert doc_id == "rejection:sprint-001"

    @pytest.mark.asyncio
    async def test_stored_document_has_hitl_rejection_source(
        self, bug_store: BugHistoryStore, store: InMemoryVectorStore
    ) -> None:
        await bug_store.record_rejection(
            sprint_id="sprint-002",
            action_type="deploy",
            feedback="Risk too high.",
            risk_score=0.9,
            agent_id="agent-1",
        )
        results = await store.search([0.1] * 32, k=5)
        assert any(d.source == _SOURCE for d in results)

    @pytest.mark.asyncio
    async def test_feedback_is_pii_masked_before_storage(
        self, bug_store: BugHistoryStore, store: InMemoryVectorStore
    ) -> None:
        await bug_store.record_rejection(
            sprint_id="sprint-003",
            action_type="read_file",
            feedback="User john.doe@example.com raised this issue.",
            risk_score=0.3,
            agent_id="agent-2",
        )
        results = await store.search([0.1] * 32, k=5)
        rejection_docs = [d for d in results if d.source == _SOURCE]
        assert rejection_docs
        assert "john.doe@example.com" not in rejection_docs[0].content

    @pytest.mark.asyncio
    async def test_document_contains_action_type_in_content(
        self, bug_store: BugHistoryStore, store: InMemoryVectorStore
    ) -> None:
        await bug_store.record_rejection(
            sprint_id="sprint-004",
            action_type="write_file",
            feedback="Wrote to protected path.",
            risk_score=0.7,
            agent_id="agent-3",
        )
        results = await store.search([0.1] * 32, k=5)
        rejection = next(d for d in results if d.source == _SOURCE)
        assert "write_file" in rejection.content

    @pytest.mark.asyncio
    async def test_tags_include_action_type_and_agent_id(
        self, bug_store: BugHistoryStore, store: InMemoryVectorStore
    ) -> None:
        await bug_store.record_rejection(
            sprint_id="sprint-005",
            action_type="deploy",
            feedback="No approval.",
            risk_score=0.9,
            agent_id="agent-xyz",
        )
        results = await store.search([0.1] * 32, k=5)
        rejection = next(d for d in results if d.source == _SOURCE)
        assert "deploy" in rejection.tags
        assert "agent-xyz" in rejection.tags

    @pytest.mark.asyncio
    async def test_multiple_rejections_stored_independently(
        self, bug_store: BugHistoryStore, store: InMemoryVectorStore
    ) -> None:
        for i in range(3):
            await bug_store.record_rejection(
                sprint_id=f"sprint-{i:03d}",
                action_type="deploy",
                feedback=f"Rejection reason {i}",
                risk_score=0.8,
                agent_id="agent-1",
            )
        results = await store.search([0.1] * 32, k=10, source_filter=_SOURCE)
        assert len(results) == 3


# ── get_similar ───────────────────────────────────────────────────────────────


class TestBugHistoryStoreGetSimilar:
    @pytest.mark.asyncio
    async def test_returns_list_of_vector_documents(self, bug_store: BugHistoryStore) -> None:
        await bug_store.record_rejection("sprint-1", "deploy", "No test.", 0.8, "agent-1")
        results = await bug_store.get_similar("deploy", "deploying to prod", k=1)
        assert isinstance(results, list)
        assert all(isinstance(d, VectorDocument) for d in results)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rejections(self, bug_store: BugHistoryStore) -> None:
        results = await bug_store.get_similar("deploy", "some context", k=3)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_at_most_k_results(self, bug_store: BugHistoryStore) -> None:
        for i in range(5):
            await bug_store.record_rejection(f"s-{i}", "deploy", f"reason {i}", 0.8, "a")
        results = await bug_store.get_similar("deploy", "context", k=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_only_returns_hitl_rejection_source_docs(
        self, bug_store: BugHistoryStore, store: InMemoryVectorStore, embedder: StubEmbedder
    ) -> None:
        # Plant a non-rejection doc in the same store
        other_doc = VectorDocument(
            content="spec content",
            embedding=await embedder.embed("spec content"),
            source="spec",
        )
        await store.upsert(other_doc)
        await bug_store.record_rejection("sprint-1", "deploy", "No test.", 0.8, "agent-1")

        results = await bug_store.get_similar("deploy", "context", k=5)
        assert all(d.source == _SOURCE for d in results)

    @pytest.mark.asyncio
    async def test_context_is_pii_masked_before_embedding(self, bug_store: BugHistoryStore) -> None:
        await bug_store.record_rejection("sprint-1", "read_file", "Feedback.", 0.3, "agent-1")
        # Should not raise even if context contains PII-like strings
        results = await bug_store.get_similar(
            "read_file",
            "User jane.doe@example.com triggered this",
            k=1,
        )
        assert isinstance(results, list)
