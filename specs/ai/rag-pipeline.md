---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-AI-010
title: RAG reference pipeline (chunk → embed → retrieve → rerank → cite → eval)
version: 0.1.0
status: draft # draft | in-review | approved | implemented | superseded
owner: ai-governance-lead
created: 2026-06-15
source: GitHub issue #271 — RAG reference pipeline spec (ADR-0081)
deployment_topology: monorepo-services # reuses existing src/memory/ + guardrails + CI
governing_adrs: [ADR-0017, ADR-0018, ADR-0019, ADR-0038, ADR-0080]
new_adrs_required: [ADR-0081-rag-reference-pipeline]
related_specs:
  [
    specs/ai/agent-memory.md,
    docs/ai/rag-quality.md,
    docs/ai/memory-governance.md,
    docs/ai/eval-scorecard.md,
  ]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-AI-010 — RAG reference pipeline

> **One-line scope.** A single governed, **opt-in reference pattern** for retrieval-augmented
> generation over the agent memory subsystem — specifying the retrieval path (chunk → embed →
> retrieve → rerank → cite → eval) that the existing memory docs leave unspecified, while
> cross-linking (not duplicating) retention governance and quality scoring.

<!-- HOW TO USE THIS TEMPLATE
  • Every numbered section is mandatory. "N/A — <reason>" where it does not apply.
  • Write code only after this spec reaches status: approved (CLAUDE.md §2).
-->

> **REFERENCE PATTERN — opt-in.** This spec is a _reference_ for workloads that need RAG. Memory
> itself is opt-in (ADR-0017); RAG is a further opt-in on top of it. **Not all workloads need
> RAG** — a project without `src/memory/`, or one whose agents do not retrieve over a corpus,
> can ignore this spec entirely. Where it applies, the **Mandatory controls (§11)** are binding.

## How `/deliver` reads this spec (section → phase)

| Spec section                                         | Feeds /deliver phase(s)                  | Gate it satisfies                                |
| ---------------------------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| §1 Context, §2 Goals, §3 Non-Goals, §4 Consumers     | 0 Intake · 1 Conception                  | problem/value/risk recorded                      |
| §5 FR, §6 NFR                                        | 2 Discovery · 4 Specification            | discovery + nfr; FR→AC traceability              |
| §6 NFR (PII rows), §11 Governance/Privacy            | 2 Discovery · 9 Security & DevSecOps     | PII classification; threat & privacy review      |
| §7 Architecture, §14 ADR Impact, `new_adrs_required` | 5 Architecture                           | ADR(s) authored & accepted                       |
| §8 Interface Contracts                               | 4 Specification · 6 Development          | contract-driven dev (Protocol interfaces)        |
| §9 Data Model                                        | 6 Development · 9 Security               | schema validation; key/injection safety          |
| §10 Golden Signals & SLO                             | 11 Observability & Operational Readiness | SLOs + PRR                                       |
| §11 Governance/Privacy/Security                      | 9 DevSecOps · 10 AI Safety               | STRIDE; AI-safety (agentic → mandatory)          |
| §12 Acceptance Criteria                              | 8 Testing · all phases                   | **becomes the dry-run evidence in FINAL-REPORT** |
| §13 Risks, §15 Open Questions                        | every phase boundary                     | surfaced as HITL items                           |

---

## 1. Context & Problem

### 1.1 Problem statement

The agent memory subsystem already ships an indexing and retrieval _substrate_ — `DocumentIndexer`
reads → masks → embeds → upserts, and `VectorStore.search()` returns top-k similar
`VectorDocument`s (`src/memory/document_indexer.py`, `src/memory/vector_store.py`). Two governance
docs cover _parts_ of RAG: `docs/ai/rag-quality.md` defines **retrieval quality** (precision@k /
recall@k / faithfulness / injection-set, mask-before-embed, treat-retrieved-as-untrusted,
ground-in-context) and `docs/ai/memory-governance.md` defines **retention/TTL, PII masking, and
deletion**. What no artefact specifies is the **end-to-end retrieval pipeline as a contract**:
chunking strategy, embedding step, retrieval (top-k), an explicit **reranking** stage, and
**citation/provenance** down to the source document, with an evaluation loop wired to the
groundedness SLI. Teams adopting RAG therefore re-derive the path ad hoc, and the reranking and
citation stages — which are not yet code — have no governing contract.

### 1.2 Research / product question

What is the single, reviewable, governed reference path a workload should follow to answer a query
from retrieved corpus content **without leaking PII, without prompt-injection via poisoned
documents, and without ungrounded ("hallucinated") claims** — and how is each stage measured?

### 1.3 Why now / motivation

`docs/ai/rag-quality.md` §"Gaps & target state" records that there is **no standing golden-query
set** and **faithfulness is not yet auto-scored**, and that the production vector store is still
pluggable (only `InMemoryVectorStore` ships). ADR-0080 / `docs/ai/eval-scorecard.md` add a
groundedness SLI on the generation side. A reference pipeline spec is the connective tissue that
ties the retrieval substrate to that eval gate, so the gaps can be closed against one contract.

### 1.4 Deployment topology decision _(decided)_

`monorepo-services`. This reuses `src/memory/`, `src/guardrails/`, the existing CI gates, and the
governance docs already in-tree. No new service is registered in `services.yaml`.

## 2. Goals & Success Metrics

| ID   | Goal                                                                                 | Measure of success                                                                                           |
| ---- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| G-01 | Specify every RAG stage (chunk→embed→retrieve→rerank→cite→eval) with I/O + a control | Each stage in §7 has inputs, outputs, and a named binding control from §11                                   |
| G-02 | Bind the pipeline to real `src/memory/` symbols, no invented APIs                    | Every cited symbol resolves in `src/memory/vector_store.py` or `document_indexer.py` (§3.6 grounding)        |
| G-03 | Make retrieval quality measurable against the eval gate                              | Eval stage emits precision@k, recall@k, faithfulness, and a groundedness SLI per `docs/ai/eval-scorecard.md` |
| G-04 | Avoid duplication of retention/quality governance                                    | §9.3 and §11 **cross-link** memory-governance.md and rag-quality.md rather than restating their tables       |

## 3. Non-Goals / Out of Scope

- **Not** a re-statement of retention/TTL or deletion/DSAR rules — those live in
  `docs/ai/memory-governance.md` and are referenced, not copied.
- **Not** a re-statement of the quality scorecard or its dimensions — those live in
  `docs/ai/rag-quality.md` (and the generation-side `docs/ai/eval-scorecard.md`).
- **Not** a mandate. RAG is opt-in; workloads without retrieval needs do not adopt this.
- **Not** a chosen production reranker or vector backend — the pipeline declares the _stage_ and
  its contract; concrete reranker/backend choices are swappable exit paths (ADR-0081).
- **Not** a generation-prompt spec — prompt externalisation is ADR-0079; this spec governs the
  retrieval path that _feeds_ the prompt.

## 4. Consumers & Personas

| Consumer                              | Need from this system                                                          |
| ------------------------------------- | ------------------------------------------------------------------------------ |
| Agent author adding RAG to a workload | A single contract for the retrieval path and its binding controls              |
| AI Governance Lead                    | Assurance that every stage has a mask/injection/grounding control and a metric |
| Reviewer of a retrieval change (PR)   | A scorecard + eval gate to fill (rag-quality.md scorecard + eval-scorecard.md) |
| SRE / on-call                         | Golden Signals on retrieval latency, hit-rate, and groundedness                |

## 5. Functional Requirements

<!-- EARS-style; each FR traces to an AC in §12. -->

| ID    | Requirement (EARS: WHEN … the system SHALL …)                                                                                                                  |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | WHEN a source document is ingested, the system SHALL chunk it into bounded, overlapping segments before embedding, preserving the source identity per chunk.   |
| FR-02 | WHEN a chunk is embedded, the system SHALL mask PII (`mask_text`) **before** calling `Embedder.embed()`, never embedding unmasked text.                        |
| FR-03 | WHEN a query is received, the system SHALL embed the (masked) query and retrieve the top-k most similar chunks via `VectorStore.search(query_embedding, k)`.   |
| FR-04 | WHEN top-k candidates are retrieved, the system SHALL apply a reranking stage that reorders candidates by query relevance before any reach the LLM prompt.     |
| FR-05 | WHEN retrieved/reranked content is assembled into a prompt, the system SHALL run `prompt_injection_guard` over that content (treat-retrieved-as-untrusted).    |
| FR-06 | WHEN an answer is produced, the system SHALL attach provenance — the `VectorDocument.source`/`id` of each cited chunk — so every claim traces to a source doc. |
| FR-07 | WHEN an answer references retrieved content, the system SHALL ground the answer in retrieved chunks and reject/flag unsupported claims (prefer "uncertain").   |
| FR-08 | WHEN a retrieval-affecting change is made (embedder, corpus, chunking, top-k, reranker), the system SHALL evaluate it against the eval gate before merge.      |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                                                                                       |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | **Privacy:** no L1/L2 PII may enter the index, a retrieved chunk, fixtures, or the golden-query set (CLAUDE.md §3.1; rag-quality.md). PII field: corpus text.     |
| NFR-02 | **Config via env:** top-k, chunk size/overlap, and reranker selection SHALL be configuration, not hard-coded, with documented defaults.                           |
| NFR-03 | **Observability:** retrieval is a child span of the reasoning step; emit retrieval latency, top-k, and hit-rate per `docs/ai/ai-observability-naming.md`.         |
| NFR-04 | **Coverage:** any implementing module SHALL have ≥ 80% unit coverage (CLAUDE.md §3.5), including an injection-set regression and a grounding test.                |
| NFR-05 | **Pluggability:** reranker and vector backend SHALL be swappable behind a `Protocol` (matching `VectorStore`/`Embedder`) without changing callers.                |
| NFR-06 | **At-rest encryption:** when a production backend stores chunk content, it SHALL use `EncryptedField` (AES-256-GCM) per ADR-0018 (as `PostgresVectorStore` does). |
| NFR-07 | **Error handling / degrade:** on retrieval-backend failure the pipeline SHALL degrade per ADR-0075 (no silent ungrounded answer; surface the gap).                |

## 7. Architecture

The pipeline is a six-stage path over the existing memory substrate. Stages 1–2 run at **index
time** (extending `DocumentIndexer`); stages 3–6 run at **query time**. Reranking (4) and citation
(5) are **new contract surface** — they have no code yet and are specified here as the governing
target.

```
INDEX TIME                                    QUERY TIME
──────────────────────────────────────        ─────────────────────────────────────────────────
source doc                                     user/agent query
   │                                              │
   ▼  (1) CHUNK                                    ▼  mask query → (3) EMBED query
bounded overlapping segments                   Embedder.embed(masked_query)
   │  per-chunk source identity preserved          │
   ▼  mask each chunk (mask_text)                   ▼  (3) RETRIEVE top-k
   ▼  (2) EMBED  Embedder.embed(masked_chunk)    VectorStore.search(query_embedding, k, source_filter?)
   ▼  upsert VectorDocument                         │   → list[VectorDocument]
VectorStore.upsert(doc)                             ▼  (4) RERANK  reorder candidates by relevance
                                                    ▼  prompt_injection_guard(retrieved text)   ← treat-as-untrusted
                                                    ▼  (5) CITE  attach VectorDocument.source/id provenance
                                                    ▼  LLM answer  grounded-in-context only
                                                    ▼  (6) EVAL  precision@k / recall@k / faithfulness / groundedness SLI
```

### Stage contracts

| Stage           | Inputs                                       | Outputs                                      | Binding control (from §11)                                 | Ties to (real symbol / doc)                                                                                |
| --------------- | -------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **1. Chunk**    | source doc text + identity                   | bounded overlapping segments, each tagged    | source identity preserved per chunk (provenance precursor) | extends `DocumentIndexer.index_file` (`src/memory/document_indexer.py`) — today indexes whole files        |
| **2. Embed**    | one chunk (text)                             | `VectorDocument{content, embedding, source}` | **mask-before-embed** (always)                             | `mask_text` (`src/guardrails/pii_filter.py`) → `Embedder.embed` → `VectorStore.upsert` (`vector_store.py`) |
| **3. Retrieve** | masked query embedding, `k`, optional source | `list[VectorDocument]` (top-k)               | input boundary validation; no user-controlled SQL          | `VectorStore.search(query_embedding, k, source_filter)` (`vector_store.py`)                                |
| **4. Rerank**   | top-k `VectorDocument`s + query              | reordered candidates                         | deterministic, no PII re-introduced; swappable (NFR-05)    | **new** `Reranker` Protocol (target; see §8) — not yet in code                                             |
| **5. Cite**     | reranked chunks                              | answer-context with per-claim provenance     | **treat-retrieved-as-untrusted** + provenance              | `prompt_injection_guard` (`src/guardrails/prompt_injection_guard.py`); `VectorDocument.source`/`.id`       |
| **6. Eval**     | query, answer, retrieved chunks, golden set  | scorecard row + groundedness SLI             | **ground-in-context**; eval gate before merge              | `docs/ai/rag-quality.md` scorecard + `docs/ai/eval-scorecard.md` (ADR-0080)                                |

### What is reused vs new

- **Reused (exists today):** `DocumentIndexer`, `VectorDocument`, `VectorStore`/`InMemoryVectorStore`/
  `PostgresVectorStore`, `Embedder`/`StubEmbedder` (all in `src/memory/`); `mask_text`,
  `prompt_injection_guard` (`src/guardrails/`).
- **New contract surface (this spec governs; no code yet):** the **chunking** sub-step inside
  indexing (today `index_file` embeds the whole file), the **`Reranker`** Protocol (stage 4), and
  the **citation/provenance** assembly (stage 5). These are the deltas an implementing workload
  builds; until then they are "target controls", not implemented behaviour.

## 8. Interface Contracts

This is a reference pattern, not a REST surface — the contract is expressed as Python `Protocol`s,
mirroring the existing `VectorStore`/`Embedder` Protocols (`src/memory/vector_store.py`). The
**Reranker** is the one new interface; the rest are existing symbols an implementing workload wires
together.

| Interface     | Signature (target)                                                                             | Status                                  |
| ------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------- |
| `Embedder`    | `async def embed(self, text: str) -> list[float]`                                              | **exists** (`vector_store.py`)          |
| `VectorStore` | `async def search(self, query_embedding, k=5, source_filter=None) -> list[VectorDocument]`     | **exists** (`vector_store.py`)          |
| `Reranker`    | `async def rerank(self, query: str, candidates: list[VectorDocument]) -> list[VectorDocument]` | **target — new** (this spec)            |
| (provenance)  | use existing `VectorDocument.source` and `VectorDocument.id`                                   | **exists** (`VectorDocument` dataclass) |

> Never hand-write a reranker that re-introduces unmasked text; chunks are already masked at
> index time and the reranker operates on `VectorDocument.content` (masked).

## 9. Data Model

### 9.1 Entities / payloads (validated at boundaries)

- `VectorDocument{ id, content (masked), embedding, source, tags, created_at }` — **exists**
  (`src/memory/vector_store.py`). The pipeline adds **no new persisted entity**; a chunk is a
  `VectorDocument` whose `content` is one segment and whose `source` carries the document identity.

### 9.2 Storage key/schema convention

- Reuses `agent_memory_documents` (migration `0003`, per `PostgresVectorStore`). Chunk identity
  SHOULD extend the existing `id` convention used by `DocumentIndexer` (`"{source}:{stem}"`) with a
  chunk ordinal (e.g. `"{source}:{stem}#{n}"`) so chunks of one doc remain greppable to that doc.

### 9.3 Retention

- **Retention / TTL: see `docs/ai/memory-governance.md`** — semantic/pgvector 90 days, Redis
  session 24h, bug-history 90 days; deletion/DSAR within 15 days. This spec does **not** restate
  those rules; chunks inherit the retention of the layer they are written to.

### 9.4 Governance/response metadata

- Each answer carries provenance metadata: the list of `(source, id)` pairs for cited chunks
  (FR-06). **Quality scoring metadata: see `docs/ai/rag-quality.md`** (scorecard fields).

## 10. Golden Signals & SLO Definitions

| Signal     | Derivation                                                    | Exposed as                        |
| ---------- | ------------------------------------------------------------- | --------------------------------- |
| Traffic    | retrievals per interval (count of `VectorStore.search` calls) | retrieval span count              |
| Latency    | retrieve + rerank wall time                                   | P50 / P95 / P99 retrieval latency |
| Error      | retrieval-backend failures / degraded (no-context) answers    | error_rate                        |
| Saturation | top-k hit-rate / index size vs corpus mtime (freshness)       | hit-rate, freshness gauge         |

Naming follows `docs/ai/ai-observability-naming.md` (retrieval latency, top-k, hit rate) and the
retrieval span is a child of the reasoning step (`skills/observability/otel-instrumentation.md`).
The **groundedness SLI** is owned by `docs/ai/eval-scorecard.md` (ADR-0080); a faithfulness/
groundedness regression flips the eval gate to a HITL review (rag-quality.md, threshold ≥ 0.7 risk
per CLAUDE.md §3.2 LLM09). Record any thresholds in `docs/sre/slo/slo.yaml`.

## 11. Governance, Privacy & Security

| Concern                                  | Control in this spec                                                                               | Maps to                                  |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Human oversight (HITL/HOTL)              | Eval-gate / faithfulness regression routes to HITL review (LLM09)                                  | ADR-0011                                 |
| PII (classify L1–L4; mask at boundaries) | **Mask-before-embed always** (`mask_text` before `Embedder.embed`); no PII in corpus/golden set    | ADR-0012, specs/privacy/, rag-quality.md |
| Injection (poisoned retrieval, LLM01)    | **Treat-retrieved-as-untrusted**: `prompt_injection_guard` over retrieved/reranked text before LLM | rag-quality.md, CLAUDE.md §3.2           |
| Grounding / hallucination (LLM09)        | **Ground-in-context**: reject claims unsupported by retrieved chunks; eval gate                    | ADR-0080, eval-scorecard.md, §3.6        |
| Auditability (immutable trail)           | Memory writes flow through audit log; provenance recorded per chunk                                | ADR-0026, memory-governance.md           |
| Retention / deletion                     | Inherited from memory layer — **see memory-governance.md** (not restated here)                     | ADR-0017, memory-governance.md           |
| At-rest encryption                       | Production backend encrypts content via `EncryptedField` (AES-256-GCM)                             | ADR-0018, ADR-0019                       |
| Pipeline security (SAST/SCA/secret/SBOM) | Parameterised `search()` SQL only — never interpolate `source_filter` (`vector_store.py` note)     | ADR-0029                                 |

> **Mandatory controls (binding when RAG is adopted), verbatim from `docs/ai/rag-quality.md`:**
> mask-before-embed · treat-retrieved-content-as-untrusted (`prompt_injection_guard`) ·
> ground-answers-in-retrieved-context · no real PII in corpus/fixtures/golden set. A STRIDE pass
> over the **retrieved-content boundary** is mandatory — it is untrusted input (Phase 10 AI Safety
> applies because this touches `src/guardrails/` usage and retrieval over agent memory).

## 12. Acceptance Criteria

| ID    | Acceptance criterion (WHEN … THEN …)                                                                                                      | Covers FR(s) |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| AC-01 | WHEN a doc is ingested THEN it is split into bounded overlapping chunks, each retaining its source identity                               | FR-01        |
| AC-02 | WHEN a chunk is embedded THEN `mask_text` ran before `Embedder.embed`; embedding unmasked text fails review                               | FR-02        |
| AC-03 | WHEN a query arrives THEN the masked query embedding drives `VectorStore.search(query_embedding, k)` returning ≤ k `VectorDocument`s      | FR-03        |
| AC-04 | WHEN top-k candidates exist THEN the `Reranker` reorders them and only the reranked set proceeds toward the prompt                        | FR-04        |
| AC-05 | WHEN retrieved content is assembled THEN `prompt_injection_guard` ran over it before it reached the LLM (injection-set regression passes) | FR-05        |
| AC-06 | WHEN an answer is returned THEN each cited claim carries `(source, id)` provenance traceable to a source doc                              | FR-06        |
| AC-07 | WHEN an answer makes a claim unsupported by retrieved chunks THEN it is rejected/flagged "uncertain — verify"                             | FR-07        |
| AC-08 | WHEN a retrieval-affecting change is proposed THEN the RAG scorecard + groundedness SLI are evaluated before merge                        | FR-08        |

> **Requirement coverage footer (gate).** 8 FRs total · 8 mapped to ≥ 1 AC · **0 unmapped**.

## 13. Risks & Limitations

- **Reranking and citation are not yet code** — they are target controls. Until implemented, a
  workload that retrieves without them is non-conformant; this is a documented gap, not hidden.
- **Only `InMemoryVectorStore` ships as a fully exercised path** (`rag-quality.md` gap); a
  production backend (`PostgresVectorStore`) must re-verify mask-before-embed + provenance before
  promotion. Trade-off recorded as an ADR-0081 consequence.
- **No standing golden-query set yet** (`rag-quality.md` gap) — the eval stage (FR-08) is
  hand-filled until the golden set + auto-scoring land alongside the eval-scorecard target.
- **Chunking changes recall** — overly small chunks fragment context, overly large dilute
  precision@k; this is why FR-08 re-evaluates on any chunking change.

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0017 (agent memory architecture), ADR-0018/ADR-0019 (encryption/TLS at rest),
  ADR-0038 (Learn-stage feedback loop, bug-history recall), ADR-0080 (groundedness SLI /
  eval-scorecard).
- **Adds:** ADR-0081 (this RAG reference pipeline — chunk/embed/retrieve/rerank/cite/eval, controls,
  opt-in, swappable reranker/backend exit paths).
- **Produces:** this spec; cross-links into `docs/ai/rag-quality.md` and
  `docs/ai/memory-governance.md`; (on implementation) a `Reranker` Protocol and chunking sub-step.

## 15. Open Questions

1. Default chunk size / overlap and default top-k — to be fixed as configurable defaults (NFR-02)
   once a golden-query set exists to tune against.
2. Which reranker class ships as the reference (cross-encoder vs lexical re-score) — left open;
   ADR-0081 makes the reranker a swappable exit path rather than picking one now.
3. Whether the golden-query set lives beside `tests/` or under `docs/ai/` — coordinate with the
   eval-scorecard / ADR-0080 owner.

## 16. References

- `specs/ai/agent-memory.md` (authoritative memory architecture) · ADR-0017
- `docs/ai/rag-quality.md` (retrieval **quality scoring** — cross-linked, not duplicated)
- `docs/ai/memory-governance.md` (retention/TTL/deletion — cross-linked, not duplicated)
- `docs/ai/eval-scorecard.md` · ADR-0080 (groundedness SLI / generation-side eval gate)
- `src/memory/vector_store.py` (`VectorStore`, `Embedder`, `VectorDocument`, `InMemoryVectorStore`,
  `PostgresVectorStore`) · `src/memory/document_indexer.py` (`DocumentIndexer`)
- `src/guardrails/pii_filter.py` (`mask_text`) · `src/guardrails/prompt_injection_guard.py`
- `docs/ai/ai-observability-naming.md` · `skills/observability/otel-instrumentation.md`
- CLAUDE.md §3.1 (privacy), §3.2 (LLM01/06/09), §3.6 (grounding & non-fabrication)
- `docs/adr/ADR-0081-rag-reference-pipeline.md`
