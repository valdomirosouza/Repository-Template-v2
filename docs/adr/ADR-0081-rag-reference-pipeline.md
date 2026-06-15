# ADR-0081 — RAG Reference Pipeline (Chunk → Embed → Retrieve → Rerank → Cite → Eval)

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** AI Governance Lead
**Spec:** specs/ai/rag-pipeline.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0017](ADR-0017-agent-memory-architecture.md), [ADR-0018](ADR-0018-db-encryption-at-rest.md), [ADR-0038](ADR-0038-learn-stage-feedback-loop.md), ADR-0080 (groundedness SLI / eval-scorecard)

---

## Context

The agent memory subsystem (ADR-0017) ships a retrieval _substrate_: `DocumentIndexer` reads →
masks → embeds → upserts documents, and `VectorStore.search()` returns top-k similar
`VectorDocument`s (`src/memory/document_indexer.py`, `src/memory/vector_store.py`). Two governance
documents cover _parts_ of retrieval-augmented generation but not the whole path:

- `docs/ai/rag-quality.md` defines **retrieval quality** — precision@k / recall@k / faithfulness /
  injection-set — and three mandatory controls (mask-before-embed, treat-retrieved-as-untrusted via
  `prompt_injection_guard`, ground-answers-in-context). It records open gaps: no standing
  golden-query set, faithfulness not yet auto-scored, only `InMemoryVectorStore` exercised.
- `docs/ai/memory-governance.md` defines **retention/TTL, PII masking, deletion/DSAR**.

What no artefact specifies is the **end-to-end retrieval pipeline as a single contract**: a
chunking strategy, the embedding step, retrieval (top-k), an explicit **reranking** stage, and
**citation/provenance** to the source document, with an evaluation loop tied to the groundedness
SLI (ADR-0080 / `docs/ai/eval-scorecard.md`). Reranking and citation have **no code yet** and no
governing contract, so teams adopting RAG re-derive the path ad hoc and the riskiest stages
(poisoned-document injection, ungrounded answers) lack a named owner. This is an architectural gap,
not a coding task.

## Decision

We will adopt **one governed reference RAG pipeline**, specified in `specs/ai/rag-pipeline.md`, with
six stages — **chunk → embed → retrieve → rerank → cite → eval** — each carrying explicit
inputs/outputs and a binding control:

1. **Chunk** (index time): split source docs into bounded, overlapping segments, preserving source
   identity per chunk (extends `DocumentIndexer.index_file`, which today indexes whole files).
2. **Embed**: mask each chunk with `mask_text` **before** `Embedder.embed()` — mask-before-embed is
   always-on; store as a `VectorDocument`.
3. **Retrieve**: embed the masked query and call `VectorStore.search(query_embedding, k, source_filter)`.
4. **Rerank**: a new swappable `Reranker` Protocol reorders top-k candidates before any reach the
   prompt.
5. **Cite**: run `prompt_injection_guard` over retrieved/reranked content (treat-retrieved-as-untrusted)
   and attach `VectorDocument.source`/`.id` provenance per cited claim.
6. **Eval**: score precision@k / recall@k / faithfulness against the RAG scorecard
   (`docs/ai/rag-quality.md`) and the groundedness SLI (ADR-0080 / `docs/ai/eval-scorecard.md`)
   before any retrieval-affecting change merges.

The pipeline is an **opt-in reference pattern**: memory is opt-in (ADR-0017) and RAG is a further
opt-in on top of it — workloads that do not retrieve over a corpus do not adopt it. Where it **is**
adopted, the three mandatory controls and "no real PII in corpus/golden set" are binding. The spec
**cross-links** retention (memory-governance.md) and quality scoring (rag-quality.md) rather than
duplicating them. The reranker and the vector backend are **swappable exit paths**, not fixed
choices.

## Consequences

### Positive

- One reviewable contract for the whole retrieval path; reranking and citation finally have an
  owner and a control instead of being undefined.
- Every stage ties to a real `src/memory/` / `src/guardrails/` symbol, so an implementing workload
  wires existing pieces plus one new `Reranker` Protocol — minimal new surface.
- The eval stage connects retrieval to the existing groundedness gate (ADR-0080), closing the loop
  between "retrieved the right chunks" and "answered faithfully".
- Opt-in scoping means non-RAG projects carry zero added obligation.

### Negative / Trade-offs

- Reranking and the chunking sub-step and citation assembly are **target controls, not implemented**;
  a workload retrieving without them is non-conformant until it builds them. The ADR records the
  target, it does not deliver the code.
- A standing golden-query set still does not exist (rag-quality.md gap), so the eval stage is
  hand-filled until auto-scoring lands — the gate is real but currently manual.
- Adding a rerank stage increases query-time latency; this must be budgeted in the Golden Signals
  (spec §10).

### Neutral

- No new persisted entity: a chunk is a `VectorDocument` whose `content` is one segment. Retention
  is inherited from the memory layer it is written to (memory-governance.md), unchanged by this ADR.

## Alternatives Considered

- **Do nothing — leave RAG as ad-hoc usage of the memory substrate.** Rejected: the two riskiest
  stages (injection via poisoned documents, ungrounded answers) and reranking/citation have no
  contract, so each adopter re-derives controls inconsistently.
- **Fold RAG guidance into `docs/ai/rag-quality.md`.** Rejected: that doc governs _quality scoring_;
  mixing the end-to-end _pipeline contract_ into it would blur the quality/pipeline boundary and
  duplicate retention rules. A dedicated spec + this ADR keeps each doc single-purpose and
  cross-linked.
- **Pick a concrete production reranker and vector backend now.** Rejected as premature: no golden
  set exists to tune against. The reranker/backend are declared as swappable Protocols (exit paths)
  so a choice can be made later without re-opening this decision.

## Compliance & Risk

- **Controls affected:** OWASP LLM01 (prompt injection over retrieved content — `prompt_injection_guard`),
  LLM06 (PII masking — `mask_text` before embed), LLM09 (grounding / faithfulness, human review at
  ≥ 0.7 risk). See `specs/security/owasp-genai-control-matrix.yaml`.
- **Data classification impact:** none new — corpus text must be masked before embedding; no L1/L2
  PII may enter the index or golden set (`docs/data/data-classification.md`).
- **Autonomy impact:** none — no HITL/HOTL or feature-flag change (ADR-0015). A faithfulness/
  groundedness regression routes to HITL review via the existing eval gate.
- **Review/expiry:** revisit when a production vector backend is promoted or a reference reranker is
  chosen (whichever first); otherwise permanent.

### Exit paths

- **Swap rerankers** behind the `Reranker` Protocol (cross-encoder ↔ lexical re-score ↔ none)
  without changing callers (spec §8, NFR-05).
- **Swap vector backends** behind the existing `VectorStore` Protocol (`InMemoryVectorStore` ↔
  `PostgresVectorStore` ↔ future backend); a new backend must re-verify mask-before-embed and
  provenance before promotion (rag-quality.md gap; spec §13).

---

## Related

- `docs/adr/README.md` — master index & lifecycle definition
- `docs/adr/adr-review-checklist.md` — checklist to apply before marking this ADR `Accepted`
- `specs/ai/rag-pipeline.md` (this decision's spec) · `docs/ai/rag-quality.md` ·
  `docs/ai/memory-governance.md` · `docs/ai/eval-scorecard.md`
- `src/memory/vector_store.py` · `src/memory/document_indexer.py` ·
  `src/guardrails/pii_filter.py` · `src/guardrails/prompt_injection_guard.py`
