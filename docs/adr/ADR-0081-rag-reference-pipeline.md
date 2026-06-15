# ADR-0081 — RAG Reference Pipeline

**Status:** Proposed
**Date:** 2026-06-15
**Authors:** Valdomiro Souza
**Spec:** specs/ai/rag-pipeline.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0017](ADR-0017-agent-memory-architecture.md) (agent memory architecture), [ADR-0038](ADR-0038-learn-stage-feedback-loop.md) (Learn-stage feedback loop / bug history)

## Context

The repository ships the _storage and governance_ layer for retrieval — `VectorStore` / `Embedder` / `DocumentIndexer` / `SessionMemory` / `BugHistoryStore` (`specs/ai/agent-memory.md`), retention / TTL / encryption rules (`docs/ai/memory-governance.md`), and a RAG quality standard with named dimensions (`docs/ai/rag-quality.md`). What was missing is a single, named contract for the retrieval **pipeline** that composes those primitives end to end: chunking → embedding governance → retrieve top-k → rerank → cite/provenance → retrieval eval. `rag-quality.md` itself flags the consequences of that gap — no standing golden query set, faithfulness not auto-scored, and only `InMemoryVectorStore` shipping with no eval gate before a production backend lands. SPEC-AI-002 (`specs/ai/rag-pipeline.md`) specifies the pipeline; this ADR records the design decision and, critically, its **scoping as a reference pattern**.

## Decision

1. **Adopt a six-stage reference pipeline.** A retrieval pipeline that adopts RAG MUST follow the stages and policies in SPEC-AI-002: fixed-size chunking with configurable overlap (provenance preserved), a single governed embedder, `top-k` retrieval over `VectorStore.search()`, an explicitly-declared rerank policy (default: similarity-order pass-through), per-answer citation from `VectorDocument` source identity, and retrieval evaluation against a standing golden query set.
2. **Scope it as a reference pattern, not a mandated build.** RAG over agent memory is opt-in (ADR-0017; the memory module is opt-in). This pipeline is normative _by reference_: it specifies how a retrieval pipeline must behave **if** a project makes RAG a core capability. No code is required to merge the spec/ADR, and projects without `src/memory/` can ignore it.
3. **Compose, do not extend.** The pipeline reuses the existing `VectorStore` / `Embedder` / `DocumentIndexer` protocols unchanged (`agent-memory.md §3`) — no new wire or Python protocol surface is introduced. Retrieval stays explicit (orchestrator calls `memory.search()` and injects results as context), never LLM-autonomous.
4. **Gate retrieval quality on a versioned golden set.** Any retrieval-affecting change (new embedder, corpus, chunking, or top-k) records precision@k / recall@k on a version-controlled golden query set in the RAG scorecard (`rag-quality.md`); an embedder identity/dimension change is gated on a re-evaluation before promotion. This closes the "no golden query set" gap and provides the eval bar a production vector backend must clear.
5. **Treat retrieved content as untrusted input.** `prompt_injection_guard.py` is applied to every retrieved chunk before it reaches the LLM (LLM01), and mask-before-embed (LLM06) is preserved from `agent-memory.md`.

## Consequences

### Positive

- One governed, copy-able contract for the full retrieve path; ad-hoc retrieval changes become measurable, reviewable events.
- Closes named gaps in `rag-quality.md` (golden set, eval gate) with an owning spec/ADR before any production backend lands.
- Zero impact on projects that do not use RAG — reference-pattern scoping keeps the template lean (ADR-0017 opt-in posture honoured).

### Negative / Trade-offs

- **Reference, not enforced.** Until a project implements the pipeline, the contract is normative-by-reference only; the eval gate binds when RAG becomes core. This is the central trade-off, accepted to avoid forcing RAG on every consumer.
- **Default no-op reranker** caps recall at the vector store's similarity ordering. Explicit and upgradable, but a real reranker is deferred.
- **Golden-set quality risk** — a weak golden set yields misleading precision@k; mitigated by version-controlling the set and reviewing it like any fixture.

### Neutral

- Stage policies (chunk size, overlap, top-k, embedder) are config-driven, so tuning is a settings change, not a code change.

## Alternatives Considered

- **Mandate RAG and ship a concrete pipeline implementation.** Rejected — contradicts the opt-in memory posture (ADR-0017) and would force the dependency on consumers that do not need retrieval.
- **Leave retrieval governed only by `rag-quality.md`.** Rejected — the quality standard names dimensions and gaps but has no pipeline-level contract, so each change stays ad hoc and the gaps have no owner.
- **Introduce a new envelope/protocol for retrieval results.** Rejected — would break the existing `VectorStore`/`Embedder` surface in `agent-memory.md`; composing the existing protocols is sufficient.

## Compliance & Risk

- **Controls affected:** LLM01 (prompt injection guard on retrieved chunks), LLM06 (mask-before-embed), LLM09 (grounding / faithfulness); OWASP A04 (bounded top-k by design).
- **Data classification impact:** none new — mask-before-embed preserved; no real PII in corpus, fixtures, or golden set.
- **Autonomy impact:** none in this change — spec/ADR only, no `src/agents/` or `src/guardrails/` code touched, so no AI-safety phase is triggered now. If a project later implements the pipeline inside those paths, Phase 10 (AI Safety) becomes mandatory for that change.
- **Review/expiry:** revisit when a production vector backend is promoted or a non-default reranker is adopted.

## Related

- `specs/ai/rag-pipeline.md` (SPEC-AI-002)
- `docs/ai/rag-quality.md` · `specs/ai/agent-memory.md` · `docs/ai/memory-governance.md`
- `docs/ai/eval-scorecard.md` · `docs/ai/ai-observability-naming.md`
- `src/guardrails/pii_filter.py` · `src/guardrails/prompt_injection_guard.py`
- ADR-0017 (agent memory architecture) · ADR-0038 (Learn-stage feedback loop)
