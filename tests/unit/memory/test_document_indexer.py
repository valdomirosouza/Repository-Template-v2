"""Unit tests for src/memory/document_indexer.py.

Spec: specs/ai/agent-memory.md §3.2
ADR:  ADR-0017 (Agent Memory Architecture)

Uses tmp_path fixtures for file I/O and InMemoryVectorStore + StubEmbedder
so no external services are required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.memory.document_indexer import DocumentIndexer, _source_tag
from src.memory.vector_store import InMemoryVectorStore, StubEmbedder

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


@pytest.fixture()
def embedder() -> StubEmbedder:
    return StubEmbedder(dim=32)


@pytest.fixture()
def indexer(store: InMemoryVectorStore, embedder: StubEmbedder) -> DocumentIndexer:
    return DocumentIndexer(vector_store=store, embedder=embedder)


# ── _source_tag ───────────────────────────────────────────────────────────────


class TestSourceTag:
    def test_spec_path_returns_spec(self, tmp_path: Path) -> None:
        p = tmp_path / "specs" / "ai" / "agent-design.md"
        assert _source_tag(p) == "spec"

    def test_adr_path_returns_adr(self, tmp_path: Path) -> None:
        p = tmp_path / "docs" / "adr" / "ADR-0001.md"
        assert _source_tag(p) == "adr"

    def test_other_path_returns_doc(self, tmp_path: Path) -> None:
        p = tmp_path / "docs" / "misc" / "readme.md"
        assert _source_tag(p) == "doc"


# ── index_file ────────────────────────────────────────────────────────────────


class TestDocumentIndexerIndexFile:
    @pytest.mark.asyncio
    async def test_indexes_file_and_returns_document(
        self, indexer: DocumentIndexer, store: InMemoryVectorStore, tmp_path: Path
    ) -> None:
        spec_dir = tmp_path / "specs"
        spec_dir.mkdir()
        f = spec_dir / "test-spec.md"
        f.write_text("# Test Spec\n\nThis is synthetic spec content.")

        doc = await indexer.index_file(f)

        assert doc.source == "spec"
        assert doc.id == "spec:test-spec"
        assert len(doc.embedding) == 32

    @pytest.mark.asyncio
    async def test_document_retrievable_after_index(
        self, indexer: DocumentIndexer, store: InMemoryVectorStore, tmp_path: Path
    ) -> None:
        f = tmp_path / "my-doc.md"
        f.write_text("# Content")

        doc = await indexer.index_file(f)

        results = await store.search(doc.embedding, k=1)
        assert len(results) == 1
        assert results[0].id == doc.id

    @pytest.mark.asyncio
    async def test_content_is_masked_before_storage(
        self, tmp_path: Path, store: InMemoryVectorStore, embedder: StubEmbedder
    ) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Contact: john.doe@example.com")
        indexer = DocumentIndexer(store, embedder)

        doc = await indexer.index_file(f)

        assert "john.doe@example.com" not in doc.content

    @pytest.mark.asyncio
    async def test_tags_contain_stem_and_source(
        self, indexer: DocumentIndexer, tmp_path: Path
    ) -> None:
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        f = adr_dir / "ADR-0017.md"
        f.write_text("# ADR-0017")

        doc = await indexer.index_file(f)

        assert "ADR-0017" in doc.tags
        assert "adr" in doc.tags


# ── index_directory ───────────────────────────────────────────────────────────


class TestDocumentIndexerIndexDirectory:
    @pytest.mark.asyncio
    async def test_indexes_all_md_files_in_directory(
        self, indexer: DocumentIndexer, tmp_path: Path
    ) -> None:
        for i in range(3):
            (tmp_path / f"doc-{i}.md").write_text(f"# Doc {i}")
        (tmp_path / "not-a-doc.txt").write_text("ignored")

        docs = await indexer.index_directory(tmp_path)

        assert len(docs) == 3

    @pytest.mark.asyncio
    async def test_skips_unreadable_files_without_raising(
        self, tmp_path: Path, store: InMemoryVectorStore, embedder: StubEmbedder
    ) -> None:
        good = tmp_path / "good.md"
        good.write_text("# Good")

        # Simulate a file that causes an error by subclassing indexer
        class FailingIndexer(DocumentIndexer):
            async def index_file(self, path: Path):
                if path.name == "bad.md":
                    raise OSError("simulated read error")
                return await super().index_file(path)

        (tmp_path / "bad.md").write_text("# Bad")
        fi = FailingIndexer(store, embedder)

        docs = await fi.index_directory(tmp_path)

        assert any(d.id.endswith("good") for d in docs)
        assert len(docs) == 1  # bad.md was skipped

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_directory(
        self, indexer: DocumentIndexer, tmp_path: Path
    ) -> None:
        docs = await indexer.index_directory(tmp_path)
        assert docs == []


# ── index_all ─────────────────────────────────────────────────────────────────


class TestDocumentIndexerIndexAll:
    @pytest.mark.asyncio
    async def test_indexes_multiple_directories(
        self, indexer: DocumentIndexer, tmp_path: Path
    ) -> None:
        specs_dir = tmp_path / "specs"
        adr_dir = tmp_path / "adr"
        specs_dir.mkdir()
        adr_dir.mkdir()
        (specs_dir / "spec.md").write_text("# Spec")
        (adr_dir / "adr.md").write_text("# ADR")

        count = await indexer.index_all(directories=[specs_dir, adr_dir])

        assert count == 2

    @pytest.mark.asyncio
    async def test_missing_directory_skipped_gracefully(
        self, indexer: DocumentIndexer, tmp_path: Path
    ) -> None:
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "doc.md").write_text("# Real")
        missing = tmp_path / "nonexistent"

        count = await indexer.index_all(directories=[real_dir, missing])

        assert count == 1
