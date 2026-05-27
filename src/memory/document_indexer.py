"""DocumentIndexer — indexes specs/ and docs/adr/ into the VectorStore.

Spec: specs/ai/agent-memory.md §3.2
ADR:  ADR-0017 (Agent Memory Architecture)

Triggered by:
  - GitHub Action on push to main (.github/workflows/index-docs.yml)
  - Manual: make memory-index

PRIVACY: spec and ADR content contains no PII by policy. pii_filter.mask_text()
is still called on content before embedding as a defence-in-depth measure.
"""

from __future__ import annotations

from pathlib import Path

from src.guardrails.pii_filter import mask_text
from src.memory.vector_store import Embedder, VectorDocument, VectorStore
from src.observability.logger import get_logger

logger = get_logger("memory.document_indexer")

_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_DIRS = [
    _REPO_ROOT / "specs",
    _REPO_ROOT / "docs" / "adr",
]


def _source_tag(path: Path) -> str:
    parts = path.parts
    if "specs" in parts:
        return "spec"
    if "adr" in parts:
        return "adr"
    return "doc"


class DocumentIndexer:
    """Scans Markdown files and upserts them into the VectorStore.

    Spec: specs/ai/agent-memory.md §3.2
    """

    def __init__(self, vector_store: VectorStore, embedder: Embedder) -> None:
        self._store = vector_store
        self._embedder = embedder

    async def index_file(self, path: Path) -> VectorDocument:
        """Read, mask, embed, and upsert a single file. Returns the VectorDocument."""
        raw = path.read_text(encoding="utf-8")
        masked = mask_text(raw)
        embedding = await self._embedder.embed(masked)

        source = _source_tag(path)
        doc = VectorDocument(
            id=f"{source}:{path.stem}",
            content=masked,
            embedding=embedding,
            source=source,
            tags=[path.stem, source],
        )
        await self._store.upsert(doc)
        logger.info("Document indexed", path=str(path), doc_id=doc.id, source=source)
        return doc

    async def index_directory(
        self,
        directory: Path,
        glob: str = "**/*.md",
    ) -> list[VectorDocument]:
        """Index all Markdown files in a directory tree."""
        docs: list[VectorDocument] = []
        for path in sorted(directory.glob(glob)):
            if path.is_file():
                try:
                    doc = await self.index_file(path)
                    docs.append(doc)
                except Exception as exc:
                    logger.warning("Failed to index file", path=str(path), error=str(exc))
        return docs

    async def index_all(self, directories: list[Path] | None = None) -> int:
        """Index specs/ and docs/adr/ (or custom dirs). Returns total count indexed."""
        dirs = directories if directories is not None else _DEFAULT_DIRS
        total = 0
        for directory in dirs:
            if not directory.exists():
                logger.warning("Index directory not found — skipping", path=str(directory))
                continue
            docs = await self.index_directory(directory)
            total += len(docs)
        logger.info("Document indexing complete", total_indexed=total)
        return total
