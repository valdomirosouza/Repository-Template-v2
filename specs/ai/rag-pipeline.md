---
id: SPEC-AI-002
title: RAG Reference Retrieval Pipeline
version: 0.1.0
status: draft
owner: valdomirojr
created: 2026-06-15
source: GitHub Issue #282 (improvement plan P1 #3)
deployment_topology: monorepo-services
governing_adrs: [ADR-0017, ADR-0038]
new_adrs_required: [ADR-0081-rag-reference-pipeline]
related_specs: [specs/ai/agent-memory.md]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-AI-002 — RAG Reference Retrieval Pipeline

**One-line scope.** Defines the end-to-end retrieval pipeline (chunk → embed → retrieve → rerank → cite → evaluate) as a **reference pattern** on top of the existing agent-memory subsystem, so any project that turns RAG into a core capability has one governed, measurable contract to follow.

> **Reference pattern, not a core deliverable.** RAG over agent memory is **opt-in** (ADR-0017; memory module is opt-in). This spec specifies _how_ a retrieval pipeline must behave if a project adopts one — it does **not** mandate that every project ship one. The storage/governance primitives it composes already exist; this spec adds the missing pipeline-level contract. No code is required to merge it.

## How `/deliver` reads this spec (section → phase)

| Spec section                    | Phase(s)                      | Gate                                  |
| ------------------------------- | ----------------------------- | ------------------------------------- |
| §5 FR, §6 NFR                   | 2 Discovery · 4 Specification | FR→AC traceability                    |
| §7 Architecture, §14 ADR Impact | 5 Architecture                | ADR-0081 authored & accepted          |
| §11 Governance/Privacy/Security | 9 DevSecOps · 10 AI Safety    | injection-resistance, PII, provenance |
| §12 Acceptance Criteria         | 8 Testing · all phases        | becomes dry-run evidence              |

## 1. Context & Problem

### 1.1 Problem statement

The repository already ships the _storage and governance_ layer for retrieval — `VectorStore`/`Embedder`/`DocumentIndexer`/`SessionMemory`/`BugHistoryStore` (`specs/ai/agent-memory.md`), retention/TTL/encryption rules (`docs/ai/memory-governance.md`), and a RAG quality bar with named dimensions (`docs/ai/rag-quality.md`). What is **missing** is a single spec that ties those primitives together into a named, reviewable _pipeline_: how text is chunked, which embedding model is governed and how it is rotated, how `top-k` and reranking are chosen, how citations/provenance are surfaced, and how retrieval quality is measured against a standing golden query set. Without it, each retrieval change is evaluated ad hoc and `rag-quality.md §"Gaps & target state"` (no golden query set, faithfulness not auto-scored, only `InMemoryVectorStore` ships) stays an open list with no owning contract.

### 1.2 Research / product question

When an agent (or a downstream RAG feature) answers from indexed documents, **how do we guarantee the retrieved context is relevant, fresh, private, injection-resistant, attributable, and measurably good** — release over release — using the memory primitives we already have?

### 1.3 Why now / motivation

This is item P1 #3 of the repository improvement plan and completes the RAG artefact set begun in Wave 11. The quality standard (`rag-quality.md`) explicitly defers the pipeline contract and the golden query set to a follow-up; this spec is that follow-up. Authoring it now — before any production vector backend lands — means the eval and provenance bar is in place to gate that promotion.

### 1.4 Deployment topology decision _(decide before Phase 1)_

`monorepo-services` — the pipeline composes existing `src/memory/` components and reuses repository CI/CD and governance. No new deployable service is introduced.

## 2. Goals & Success Metrics

| ID   | Goal                                                           | Measure of success                                                                                                                     |
| ---- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| G-01 | One governed reference contract for the full retrieve pipeline | This spec covers all six stages (chunk, embed, retrieve, rerank, cite, eval) and is linked from `rag-quality.md` and `agent-memory.md` |
| G-02 | Retrieval quality is measurable, not anecdotal                 | A standing golden query set exists with precision@k / recall@k recorded per retrieval change (closes `rag-quality.md` gap #1)          |
| G-03 | Embedding-model changes are governed, not silent               | Embedder identity + dimension are pinned in the dependency manifest and a change triggers re-eval before promotion                     |
| G-04 | Every answer is attributable                                   | Each retrieved chunk carries source identity usable for citation (provenance dimension)                                                |

## 3. Non-Goals / Out of Scope

- **Re-stating storage, retention, TTL, or encryption rules.** Those are owned by `docs/ai/memory-governance.md` and `specs/ai/agent-memory.md` and are referenced, not duplicated, here.
- **Mandating a production vector backend.** Backend selection/promotion remains governed by `agent-memory.md` (`PostgresVectorStore`) and ADR-0017; this spec only sets the eval/provenance bar that promotion must clear.
- **Generation/answer-quality scoring.** Owned by `docs/ai/eval-scorecard.md`; this spec scores _retrieval_, and references faithfulness only where it bridges the two.
- **Shipping a concrete reranker or embedder implementation.** This is a reference contract; implementations are project-specific and out of scope (no code required to merge).
- **Building the CI auto-eval job.** Specifying the golden-set contract is in scope; wiring the leaderboard into CI is a tracked follow-up (§15).

## 4. Consumers & Personas

| Consumer                                | Need                                                                                                  |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| AgentOrchestrator (Reason phase)        | Relevant, masked, attributable context injected before the LLM prompt (`agent-memory.md` recall flow) |
| AI Governance Lead                      | A reviewable quality bar and golden-set scorecard per retrieval change                                |
| Engineer adopting RAG as a core feature | A copy-able reference pipeline with explicit stage policies                                           |
| Security Lead                           | Assurance that retrieved content is treated as untrusted input (LLM01)                                |

## 5. Functional Requirements

| ID    | Requirement (EARS: WHEN … system SHALL …)                                                                                                                                                                                                           |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | WHEN a source document is ingested, the system SHALL split it into chunks of a configured target size with a configured overlap before embedding, preserving chunk → source-document provenance.                                                    |
| FR-02 | WHEN a chunk is embedded, the system SHALL embed only PII-masked text (mask-before-embed; `agent-memory.md` §2), using the governed embedder pinned in the dependency manifest.                                                                     |
| FR-03 | WHEN the embedding model (identity or output dimension) changes, the system SHALL require a retrieval re-evaluation against the golden query set before the new embedder is promoted.                                                               |
| FR-04 | WHEN a query is issued, the system SHALL retrieve the top-k most similar chunks (k configurable) via `VectorStore.search()`, where each result carries its source identity.                                                                         |
| FR-05 | WHEN more than k candidates are retrievable, the system SHALL apply the declared rerank policy (default: similarity-ordered, no external reranker) before returning the final k.                                                                    |
| FR-06 | WHEN retrieved chunks are assembled into an LLM prompt, the system SHALL pass each chunk through `prompt_injection_guard.py` (retrieved content is untrusted; LLM01) before it reaches the LLM.                                                     |
| FR-07 | WHEN an answer is produced from retrieved context, the system SHALL expose, per answer, the source identity of each contributing chunk so the answer is citable (provenance).                                                                       |
| FR-08 | WHEN a retrieval-affecting change is proposed (new embedder, corpus, chunking, or top-k), the system SHALL record precision@k / recall@k (and faithfulness where bridged) on the standing golden query set in the RAG scorecard (`rag-quality.md`). |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                                                                                                                                                  |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | **Configuration via env.** Chunk size, overlap, top-k, and embedder identity SHALL be configurable settings (Pydantic Settings) with documented defaults — never hard-coded at call sites.                                   |
| NFR-02 | **No real PII** in the corpus, fixtures, or the golden query set (CLAUDE.md §3.1; `rag-quality.md` mandatory controls).                                                                                                      |
| NFR-03 | **Observability.** Retrieval SHALL emit a child span under the agent reasoning step with retrieval latency, top-k, and hit-rate per `docs/ai/ai-observability-naming.md` and `skills/observability/otel-instrumentation.md`. |
| NFR-04 | **Determinism of eval.** The golden query set and its expected-relevant labels SHALL be version-controlled so precision@k / recall@k are reproducible across runs.                                                           |
| NFR-05 | **Grounding.** The pipeline SHALL prefer "uncertain — verify" over unsupported claims; the evaluator rejects answer claims not supported by retrieved chunks (CLAUDE.md §3.6, LLM09).                                        |
| NFR-06 | **Backward compatibility.** This reference pattern SHALL NOT change the existing `VectorStore`/`Embedder` protocol surface in `agent-memory.md`; it composes them.                                                           |

## 7. Architecture

The pipeline is a thin, governed composition over existing `src/memory/` primitives. Two phases: an **offline indexing path** (ingest → chunk → mask → embed → upsert) and an **online retrieval path** (query → mask → embed → search → rerank → injection-guard → cite → evaluate).

```
INDEXING (offline, DocumentIndexer-driven)
  source doc ──► chunk(size, overlap) ──► pii_filter.mask ──► Embedder.embed ──► VectorStore.upsert
                     │                                                              (VectorDocument:
                     └─ retains source identity ─────────────────────────────────►  id, content, source)

RETRIEVAL (online, Orchestrator Reason phase)
  query ─► mask ─► embed ─► VectorStore.search(top-k) ─► rerank(policy) ─► prompt_injection_guard
                                     │                                            │
                                     └──── each chunk keeps source identity ──────┴─► LLM prompt
                                                                                       │
                                                                                       ▼
                                                                          answer + per-chunk citations

EVALUATION (per retrieval-affecting change)
  golden query set ─► run retrieval ─► precision@k / recall@k / injection-set / faithfulness ─► RAG scorecard
```

Stage policies:

- **Chunking** — fixed-size with overlap; `chunk_size` and `chunk_overlap` are config. Overlap preserves cross-boundary context; chunk → source mapping is preserved for provenance (FR-01, FR-07).
- **Embedding governance** — a single governed `Embedder`; its identity and output dimension are pinned in `docs/dependency-manifest.yaml`. A change is a governed event (FR-03) and re-runs eval before promotion.
- **Retrieve** — `VectorStore.search(embedding, k)`; `top_k` is config (FR-04). No protocol change (NFR-06).
- **Rerank** — default policy is similarity-order pass-through (no external reranker), declared explicitly so a future cross-encoder/MMR reranker is an additive, governed change, not a silent one (FR-05).
- **Cite/provenance** — `VectorDocument` already retains source identity; the pipeline surfaces it per answer (FR-07).
- **Evaluate** — golden query set + precision@k/recall@k recorded in the RAG scorecard (`rag-quality.md`); faithfulness bridges to generation eval (`eval-scorecard.md`).

Alignment: this composition does not alter the recall sequence in `agent-memory.md` (orchestrator calls `memory.search()` and injects results as context — retrieval is explicit, never LLM-autonomous).

## 8. Interface Contracts _(gate: contract-driven dev)_

N/A — no new REST/AsyncAPI surface. The pipeline composes the existing in-process `VectorStore`, `Embedder`, and `DocumentIndexer` Python protocols defined in `specs/ai/agent-memory.md §3`; this spec adds no new wire contract and intentionally does not redefine those signatures.

## 9. Data Model

### 9.1 Entities / payloads (validated at boundaries)

Reuses `VectorDocument` (`id`, `content` [PII-masked before storage], `embedding`, source identity) from `agent-memory.md §3.1`. The pipeline adds two **conceptual** payloads (project-defined, no schema mandated here):

- **Chunk** — `{ source_id, ordinal, text (masked), char_span }` produced by the chunking stage.
- **Golden query** — `{ query, expected_relevant_source_ids[], k }` for eval. No PII (NFR-02).

### 9.2 Storage key/schema convention

Inherited from `agent-memory.md` / `memory-governance.md` — not redefined here. Chunk identity SHALL be derivable from `(source_id, ordinal)` so re-indexing is idempotent.

### 9.3 Retention

Governed by `docs/ai/memory-governance.md` (semantic memory TTL 90 days, etc.). **Referenced, not restated.** The golden query set is a test fixture, not memory, and is retained in version control.

### 9.4 Governance/response metadata (if applicable)

Each retrieval response carries, per chunk: source identity (for citation) and retrieval similarity score. No additional PII-bearing metadata is introduced.

## 10. Golden Signals & SLO Definitions _(gate: observability)_

| Signal     | Derivation                                                              | Exposed         |
| ---------- | ----------------------------------------------------------------------- | --------------- |
| Traffic    | `memory_vector_searches_total{source}` (existing, `agent-memory.md §5`) | counter         |
| Latency    | retrieval child-span duration                                           | P50 / P95 / P99 |
| Error      | failed `search()` calls / total                                         | error_rate      |
| Saturation | top-k vs configured cap; index build lag vs source mtime (freshness)    | gauge           |

Quality (release-gate, not runtime SLO): precision@k / recall@k on the golden set, injection-set pass rate, faithfulness — recorded in the RAG scorecard per change. No new runtime SLO row is proposed; this spec ties into existing memory metrics.

## 11. Governance, Privacy & Security _(gate: threat & privacy review)_

| Concern                                  | Control in this spec                                                                     | Maps to                                                |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Human oversight (HITL/HOTL)              | Retrieval feeds context only; actions still route through the HITL gateway unchanged     | ADR-0011                                               |
| PII (classify L1–L4; mask at boundaries) | Mask-before-embed (FR-02); no real PII in corpus/golden set (NFR-02)                     | ADR-0012, `agent-memory.md §2`, `memory-governance.md` |
| Auditability (immutable trail)           | Retrieval scorecard recorded per change; existing memory metrics emitted                 | ADR-0026                                               |
| Authn / abuse (injection)                | `prompt_injection_guard.py` on every retrieved chunk (FR-06) — poisoned-document defence | `specs/security/threat-model.md`, LLM01                |
| Cost envelope                            | top-k and embedder are bounded/config (NFR-01)                                           | ADR-0020                                               |
| Pipeline security (SAST/SCA/secret/SBOM) | Inherited from repo pipeline; embedder pinned in manifest                                | ADR-0029                                               |

STRIDE note on the untrusted-input boundary: the retrieved chunk is the primary untrusted-input surface (Tampering/Elevation via prompt injection). It is mitigated by mandatory `prompt_injection_guard.py` (FR-06) and by treating retrieval output as context, never as an instruction channel. This spec touches no `src/agents/` or `src/guardrails/` code; if a project later implements the pipeline inside those paths, Phase 10 (AI Safety) becomes mandatory for that change.

## 12. Acceptance Criteria _(gate: dry-run validation)_

| ID    | Acceptance criterion (WHEN … THEN …)                                                                                                                                   | Covers FR(s)        |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| AC-01 | WHEN this spec is reviewed, THEN it documents an explicit policy for all six stages (chunk, embed, retrieve, rerank, cite, eval), each with a named config or default. | FR-01, FR-04, FR-05 |
| AC-02 | WHEN an embedding is computed in the reference pipeline, THEN its input is PII-masked text only (mask-before-embed).                                                   | FR-02               |
| AC-03 | WHEN the governed embedder identity or dimension changes, THEN the change is gated on a golden-set re-evaluation before promotion.                                     | FR-03               |
| AC-04 | WHEN a query is run, THEN exactly top-k source-attributed chunks are returned after the declared rerank policy.                                                        | FR-04, FR-05        |
| AC-05 | WHEN retrieved chunks are assembled for the LLM, THEN each has passed `prompt_injection_guard.py`.                                                                     | FR-06               |
| AC-06 | WHEN an answer is produced, THEN each contributing chunk's source identity is exposed for citation.                                                                    | FR-07               |
| AC-07 | WHEN a retrieval-affecting change is proposed, THEN precision@k / recall@k on the standing golden query set are recorded in the RAG scorecard.                         | FR-08               |

**Requirement coverage footer (gate).** 8 FRs total · 8 mapped to ≥ 1 AC · **0 unmapped ✅**.

## 13. Risks & Limitations

- **Reference pattern, not enforced code.** Until a project implements the pipeline, this spec is normative-by-reference only; the eval gate (FR-03, FR-08) binds when RAG becomes a core feature. Documented as the central trade-off in ADR-0081.
- **Golden-set quality risk.** A weak or unrepresentative golden query set yields misleading precision@k. Mitigated by version-controlling the set (NFR-04) and reviewing it like any spec fixture.
- **Embedding drift.** Silent embedder upgrades can degrade retrieval; mitigated by manifest pinning + re-eval gate (FR-03), consistent with ADR-0051 (model behavioural contracts) in spirit.
- **Default no-op reranker.** Shipping similarity-order as the default rerank means recall ceiling equals the vector store's; this is explicit and upgradable (FR-05), not hidden.

## 14. ADR & Dependency Impact

- **New ADR:** ADR-0081 — RAG Reference Pipeline (Status: Proposed) records the architecture decision and the reference-pattern scoping. Registered in `docs/adr/README.md`.
- **Reused ADRs:** ADR-0017 (agent memory architecture), ADR-0038 (Learn-stage feedback loop / bug history).
- **Dependency manifest:** the governed embedder identity/dimension is pinned in `docs/dependency-manifest.yaml` when a project adopts the pipeline (FR-03).

## 15. Open Questions

1. Should the golden-set auto-eval leaderboard be wired into CI as a sibling of the generation eval-scorecard target (closes `rag-quality.md` gap #1)? — tracked as follow-up, out of scope here.
2. Which reranker (cross-encoder vs MMR) becomes the recommended non-default? — deferred until a production vector backend lands.
3. Should faithfulness scoring move from "tracked" to a hard release gate once auto-scored? — bridges to `eval-scorecard.md`.

## 16. References

- `specs/ai/agent-memory.md` — VectorStore / Embedder / DocumentIndexer / SessionMemory / BugHistoryStore (SPEC-agent-memory, ADR-0017)
- `docs/ai/rag-quality.md` — RAG quality dimensions, mandatory controls, RAG scorecard, gaps & target state (**automated-eval** target)
- `docs/ai/memory-governance.md` — retention / TTL / encryption (referenced, not restated)
- `docs/ai/eval-scorecard.md` — generation-quality scoring (faithfulness bridge)
- `docs/ai/ai-observability-naming.md` · `skills/observability/otel-instrumentation.md` — retrieval span/metric conventions
- `src/guardrails/pii_filter.py` · `src/guardrails/prompt_injection_guard.py`
- `docs/adr/ADR-0081-rag-reference-pipeline.md`
- CLAUDE.md §3.1 (privacy), §3.2 (LLM01/06/09), §3.6 (grounding & non-fabrication)
