# NFR Taxonomy — Consolidated Reference Standard

> **Owner:** Product Owner + Tech Lead | **Phase:** 2 (Discovery) · 4 (Specification)
> **Status:** Approved | **Refs:** issue #275
> **Governance:** `docs/process/HITL-GOVERNANCE.md`

This is the **single reference taxonomy** for Non-Functional Requirements (NFRs) in this
repository. Use it to classify every NFR in a spec's §6 so requirements are comparable across
specs and each one traces to a real piece of evidence (an SLO, a control matrix, a test).

A category here is only worth declaring if it maps to **evidence/a gate**. An NFR with no
instrument is a wish, not a requirement (the same rule the discovery `success-metrics.md`
template applies to product metrics).

---

## How to use

1. For each row in a spec's §6 NFR table, pick the category below that fits and reference it
   (e.g. write `[performance]` or cite the category) in the requirement text.
2. Phrase the NFR as a **measurable budget**, not an adjective ("p95 ≤ 200 ms", not "fast").
3. Point at the evidence/gate column so the reviewer can check it.

The categories were grounded against vocabulary the repo already uses (`specs/`, `docs/sre/`,
`docs/privacy/`); the **AI-safety** and **human-oversight** categories apply only when the AI
Agents extension is active (`src/agents/` present).

---

## Core categories

| Category            | One-line definition                                                             | Example NFR phrasing                                                                | Typical evidence / gate it maps to                                                                                |
| ------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Performance**     | Latency/throughput budgets under defined load.                                  | "`GET /analytics` returns within p95 ≤ 200 ms / p99 ≤ 1 s at 600 req/min/key."      | Golden Signals latency SLO in `docs/sre/slo/slo.yaml`; spec §10; load test.                                       |
| **Availability**    | Proportion of time the service serves requests successfully.                    | "Ingestion API ≥ 99.9% monthly availability."                                       | SLO + error budget (`docs/sre/slo/slo.yaml`); probe strategy (`skills/sre/probe-strategy.md`).                    |
| **Reliability**     | Correct behaviour under failure (retries, idempotency, graceful degradation).   | "Store connection/timeout errors handled explicitly; no data loss on worker crash." | Integration/chaos tests; in-memory fallback pattern (CLAUDE.md §0.1); spec §9 retention.                          |
| **Scalability**     | Ability to absorb load growth via horizontal/vertical scaling and backpressure. | "Queue applies non-blocking backpressure; drops are counted, never silent."         | Capacity plan (`skills/sre/capacity-planning.md`); HPA config; `gs_queue_dropped_total` metric.                   |
| **Security**        | Resistance to the OWASP Top 10 at every boundary.                               | "All inputs validated at boundary; parameterized queries; auth on all write paths." | OWASP ASVS matrix `specs/security/asvs-control-matrix.yaml`; threat model `specs/security/threat-model.md`; DAST. |
| **Privacy**         | Lawful, minimised handling of personal data; masking before persist/log/LLM.    | "Client IPs masked (L2) before any field is persisted or logged."                   | PII classification `docs/privacy/pii-inventory.md`; DPIA/RIPD (`docs/privacy/`); `src/guardrails/pii_filter.py`.  |
| **Compliance**      | Conformance to regulatory/audit regimes (LGPD, GDPR, SOX, ISO 27001).           | "Every financial write path produces an immutable audit record."                    | LGPD/GDPR/SOX/ISO skills (CLAUDE.md §4, §10, §11); audit immutability ADR-0026.                                   |
| **Cost (FinOps)**   | Per-request / per-tenant spend stays within an allocated envelope.              | "Cost per 1k analytics queries ≤ budget; token spend per request capped."           | FinOps spec `specs/sre/finops.md`; ADR-0020; FinOps dashboard.                                                    |
| **Operability**     | Ease of deploy, configure, roll back, and run the service.                      | "All config via env vars with documented defaults (`.env.example`)."                | Deploy/rollback skill; runbooks (`docs/sre/`); config layer `src/shared/config.py`.                               |
| **Observability**   | The service exposes the signals needed to detect and diagnose issues.           | "Structured JSON logs with a propagated trace id on every request."                 | OTel/Golden Signals (`skills/observability/otel-instrumentation.md`); spec §10; Prometheus `/metrics`.            |
| **Maintainability** | Code is testable, covered, and changeable without regression.                   | "Unit coverage ≥ 80% on core logic; no hidden global state."                        | Coverage gate (CLAUDE.md §3.5); test integrity gate (ADR-0065); `skills/engineering/testing-strategy.md`.         |
| **Portability**     | Runs on the supported runtime/topology without host-specific assumptions.       | "All services containerised; runtime pinned to the supported JDK/Python version."   | Containerisation (spec §0/§7); pinned deps + SBOM (ADR-0029); `make sbom`.                                        |

## AI-feature categories _(only when `src/agents/` is present)_

| Category            | One-line definition                                                          | Example NFR phrasing                                                                 | Typical evidence / gate it maps to                                                                          |
| ------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| **AI-safety**       | Guardrails against the OWASP LLM Top 10 (injection, leakage, unsafe output). | "Prompt-injection guard always on; LLM output sanitized before render/execute."      | OWASP GenAI matrix `specs/security/owasp-genai-control-matrix.yaml`; abuse-case suite (ADR-0050); ADR-0072. |
| **Human-oversight** | Real-world agent actions route through HITL/HOTL per the autonomy level.     | "All consequential agent actions route through the HITL gateway unless flag allows." | HITL gateway `src/agents/hitl_gateway.py`; autonomy flags (ADR-0015); HITL-HOTL model ADR-0011.             |

---

## Relationship to the spec template

`specs/SPEC-TEMPLATE.md` §6 (Non-Functional Requirements) is the binding place where NFRs are
recorded per feature. Classify each §6 row by a category above. The PII-bearing rows additionally
feed §11 (Governance/Privacy/Security) and any DPIA/RIPD review.

## Related

- `specs/SPEC-TEMPLATE.md` — §6 NFR table (binding template)
- `docs/product/acceptance-criteria-standard.md` — Gherkin AC standard (companion)
- `docs/adr/ADR-0072-versioned-security-control-matrices.md` — authoritative OWASP mapping
- `docs/sre/slo/slo.yaml` · `specs/sre/finops.md` · `docs/privacy/pii-inventory.md`
