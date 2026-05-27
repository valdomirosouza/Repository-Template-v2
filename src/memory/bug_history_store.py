"""BugHistoryStore — records HITL rejection patterns as searchable vector documents.

Spec: specs/ai/agent-memory.md §3.4
ADR:  ADR-0017 (Agent Memory Architecture)
DPIA: docs/privacy/dpia/dpia-agent-memory.md

Purpose: when an agent is about to attempt an action type that was previously
rejected by HITL, it can retrieve similar past rejections via get_similar()
and adjust its approach before submission — reducing repeated escalations.

PRIVACY INVARIANT: feedback and context passed to record_rejection() and
get_similar() MUST be pii_filter-masked by the caller before passing here.
The store applies mask_text() as a defence-in-depth second pass.
"""

from __future__ import annotations

from src.guardrails.pii_filter import mask_text
from src.memory.vector_store import Embedder, VectorDocument, VectorStore
from src.observability.logger import get_logger

logger = get_logger("memory.bug_history_store")

_SOURCE = "hitl_rejection"


class BugHistoryStore:
    """Stores and retrieves HITL rejection patterns via semantic similarity.

    Spec: specs/ai/agent-memory.md §3.4
    """

    def __init__(self, vector_store: VectorStore, embedder: Embedder) -> None:
        self._store = vector_store
        self._embedder = embedder

    async def record_rejection(
        self,
        sprint_id: str,
        action_type: str,
        feedback: str,
        risk_score: float,
        agent_id: str,
    ) -> str:
        """Persist a HITL rejection as a searchable vector document.

        Returns the document ID.

        PRIVACY: feedback is masked with pii_filter before embedding and storage.
        """
        masked_feedback = mask_text(feedback)
        content = (
            f"action_type: {action_type}\n"
            f"agent_id: {agent_id}\n"
            f"risk_score: {risk_score:.2f}\n"
            f"feedback: {masked_feedback}"
        )
        embedding = await self._embedder.embed(content)

        doc = VectorDocument(
            id=f"rejection:{sprint_id}",
            content=content,
            embedding=embedding,
            source=_SOURCE,
            tags=[action_type, agent_id, f"risk:{risk_score:.1f}"],
        )
        doc_id = await self._store.upsert(doc)

        logger.info(
            "HITL rejection recorded in bug history",
            sprint_id=sprint_id,
            action_type=action_type,
            doc_id=doc_id,
        )
        return doc_id

    async def get_similar(
        self,
        action_type: str,
        context: str,
        k: int = 3,
    ) -> list[VectorDocument]:
        """Retrieve the k most semantically similar past rejections.

        PRIVACY: context is masked with pii_filter before embedding.
        """
        masked_context = mask_text(context)
        query_text = f"action_type: {action_type}\ncontext: {masked_context}"
        query_embedding = await self._embedder.embed(query_text)

        results = await self._store.search(
            query_embedding=query_embedding,
            k=k,
            source_filter=_SOURCE,
        )

        logger.info(
            "Bug history similarity search",
            action_type=action_type,
            results_count=len(results),
        )
        return results
