# RAG Quality Standard

> **Owner:** AI Governance Lead · **Status:** Living standard · **Last updated:** 2026-06-14
> Defines how retrieval-augmented generation (RAG) over the agent memory subsystem is kept correct,
> private, and measurable. It formalises the guarantees the memory layer already enforces
> (PII masking before embedding, append-and-search store) into a reviewable quality bar. Completes the
> Wave 11 (AI-Native Production) artefact set of the repository improvement plan. Memory is opt-in
> (ADR-0017); projects without `src/memory/` can ignore this.

## What exists today (`src/memory/`)

| Component                | File                   | Role                                                            |
| ------------------------ | ---------------------- | --------------------------------------------------------------- |
| `VectorStore` (Protocol) | `vector_store.py`      | Append-and-`search()` store for document embeddings             |
| `Embedder` (Protocol)    | `vector_store.py`      | Text → float vector; **input must be PII-masked by the caller** |
| `DocumentIndexer`        | `document_indexer.py`  | Read → **mask** → embed → upsert a file or directory            |
| `SessionMemory`          | `session_memory.py`    | Per-session conversational memory                               |
| `BugHistoryStore`        | `bug_history_store.py` | Prior-bug recall for the Learn stage (ADR-0038)                 |

The retrieval contract is small and explicit on purpose: indexing **masks content before embedding**
(`document_indexer.index_file` → mask → `embed`), and `Embedder.embed()` documents that its input must
already be PII-masked. RAG quality is built on top of that contract.

## Quality dimensions

RAG answers fail in ways generation alone does not. Each release that changes retrieval, the embedder,
the index corpus, or chunking must hold these:

| Dimension                    | What it checks                                                             | How                                                                                                    |
| ---------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Privacy**                  | No L1/L2 PII enters the index or a retrieved chunk                         | `pii_filter` runs before `embed()` (already wired); verify in `tests/` that masking precedes embedding |
| **Grounding / faithfulness** | The answer is supported by retrieved chunks, not invented (CLAUDE.md §3.6) | Evaluator checks answer ⊆ retrieved context; flag unsupported claims                                   |
| **Relevance**                | Top-k retrieved chunks are on-topic for the query                          | precision@k / recall@k on a golden query set                                                           |
| **Freshness**                | Index reflects current source docs; stale chunks are re-indexed            | track index build time vs source mtime                                                                 |
| **Injection resistance**     | Retrieved content cannot hijack the prompt (LLM01)                         | `prompt_injection_guard.py` applied to retrieved text before it reaches the LLM                        |
| **Provenance**               | Every retrieved chunk traces to a source doc                               | `VectorDocument` retains source identity for citation                                                  |

## Mandatory controls (binding)

- **Mask before embed — always.** Never call `Embedder.embed()` on unmasked text. PII must be filtered
  at index time (`document_indexer`) _and_ the masking guarantee re-checked for any new ingestion path
  (CLAUDE.md §3.1, LLM06).
- **Treat retrieved content as untrusted input.** Run `prompt_injection_guard.py` over retrieved
  chunks before they enter the LLM prompt — a poisoned document is an injection vector (LLM01).
- **Ground answers in retrieved context.** The Evaluator must reject an answer whose claims are not
  supported by the retrieved chunks; prefer "uncertain — verify" over invention (§3.6, LLM09).
- **No real PII in the corpus, fixtures, or golden set** (§3.1).

## Evaluating a retrieval change

Fill the scorecard below per change (new embedder, new corpus, new chunking, new top-k) and attach to
the PR. It complements — not replaces — `docs/ai/eval-scorecard.md` (which scores generation).

```text
RAG Scorecard — {embedder/corpus/chunking @ vX}
Date: YYYY-MM-DD   Evaluated by: {name}   Baseline: {prior config}

Golden query set: {n} queries
  precision@k:   0.__   recall@k:   0.__   (k = __)
  faithfulness:  0.__   (answer supported by retrieved chunks)
  injection set: {pass}/{total}  (poisoned docs must not alter the action)
  PII leakage:   0 expected  (masking precedes embedding — must be 0)

Latency:  retrieval p95 {n}ms   end-to-end p99 {n}s   Δ vs baseline {±}
Decision: APPROVE / REJECT   Rationale: ...
```

**Regression rules:** faithfulness and precision@k must not drop ≥ 0.05 vs baseline; PII-leakage and
injection-resistance are zero-tolerance — any failure blocks the change.

## Observability

Emit retrieval metrics under the conventions in `docs/ai/ai-observability-naming.md` (retrieval
latency, top-k, hit rate) and trace retrieval as a child span of the agent's reasoning step per
`skills/observability/otel-instrumentation.md`. Hallucination/faithfulness scoring is tracked there as
a target metric.

## Gaps & target state (not yet implemented)

- **No standing golden query set or RAG leaderboard** yet — the scorecard above is filled by hand.
  Target: a golden set + the scorecard auto-generated in CI, sibling to the eval-scorecard target.
- **Faithfulness is not yet auto-scored** — tracked under `docs/ai/ai-observability-naming.md`.
- **Production vector store is pluggable** — only `InMemoryVectorStore` ships; a real backend must
  re-verify the mask-before-embed and provenance guarantees above before promotion.

---

## Related

- `src/memory/` — `vector_store.py`, `document_indexer.py`, `session_memory.py`, `bug_history_store.py`
- ADR-0017 (agent memory architecture) · ADR-0038 (Learn-stage feedback loop)
- `docs/ai/eval-scorecard.md` · `docs/ai/memory-governance.md` · `docs/ai/ai-observability-naming.md`
- `src/guardrails/pii_filter.py` · `src/guardrails/prompt_injection_guard.py`
- CLAUDE.md §3.1 (privacy), §3.2 (LLM01/06/09), §3.6 (grounding & non-fabrication)
