# Architecture Decision Records (ADRs)

ADRs capture significant architectural decisions made during the evolution of this system.
Every decision that affects the overall structure, key dependencies, or operational
characteristics of the system must be recorded here.

ADRs are **binding** — implementation must align with accepted ADRs unless superseded
by a newer ADR. Changing an accepted decision requires filing a new ADR, not editing
the existing one.

---

## ADR Lifecycle

```
Proposed → Accepted → Deprecated → Superseded
```

| Status         | Meaning                                           |
| -------------- | ------------------------------------------------- |
| **Proposed**   | Under discussion; not yet binding                 |
| **Accepted**   | Binding; implementation must follow this decision |
| **Deprecated** | No longer recommended; kept for historical record |
| **Superseded** | Replaced by a newer ADR (link provided)           |

---

## ADR Template

Copy [`ADR-TEMPLATE.md`](ADR-TEMPLATE.md) to `docs/adr/ADR-NNNN-<kebab-title>.md`, fill it in, and
add a row to the master index below. Before moving an ADR `Proposed → Accepted`, run through
[`adr-review-checklist.md`](adr-review-checklist.md).

The minimal skeleton (the template adds an optional Compliance & Risk section and guidance):

```markdown
# ADR-NNNN — Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNNN
**Date:** YYYY-MM-DD
**Authors:** Name(s)

## Context

What situation or problem prompted this decision? What constraints apply?

## Decision

What was decided? State it clearly and unambiguously.

## Consequences

### Positive

What does this decision enable?

### Negative / Trade-offs

What does this decision cost or constrain?

## Alternatives Considered

What other options were evaluated and why were they rejected?
```

> ADRs are **append-only and immutable** (ADR-0059): supersede a decision with a new ADR and mark the
> old one `Superseded by ADR-NNNN` in place — never delete, move, or rewrite an accepted ADR.

---

## Master Index

### Core Architecture

These ADRs apply to every project using this template, regardless of whether the AI Agents Module is enabled.

| ADR                                                                        | Title                                                                                    | Status     | Date       |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------- | ---------- |
| [ADR-0001](ADR-0001-monorepo-structure-and-governance.md)                  | Monorepo Structure and Governance                                                        | Accepted   | 2026-05-24 |
| [ADR-0002](ADR-0002-technology-stack-selection.md)                         | Technology Stack Selection                                                               | Accepted   | 2026-05-24 |
| [ADR-0003](ADR-0003-async-api-strategy.md)                                 | Async API Strategy                                                                       | Accepted   | 2026-05-24 |
| [ADR-0004](ADR-0004-observability-stack.md)                                | Observability Stack                                                                      | Accepted   | 2026-05-24 |
| [ADR-0005](ADR-0005-message-broker-selection.md)                           | Message Broker Selection                                                                 | Accepted   | 2026-05-24 |
| [ADR-0006](ADR-0006-deployment-strategy.md)                                | Deployment Strategy                                                                      | Accepted   | 2026-05-24 |
| [ADR-0007](ADR-0007-service-mesh.md)                                       | Service Mesh                                                                             | Proposed   | 2026-05-24 |
| [ADR-0008](ADR-0008-secrets-management.md)                                 | Secrets Management                                                                       | Accepted   | 2026-05-24 |
| [ADR-0009](ADR-0009-caching-strategy.md)                                   | Caching Strategy                                                                         | Accepted   | 2026-05-24 |
| [ADR-0012](ADR-0012-pii-masking-strategy.md)                               | PII Masking Strategy                                                                     | Accepted   | 2026-05-24 |
| [ADR-0013](ADR-0013-data-retention-policy.md)                              | Data Retention Policy                                                                    | Accepted   | 2026-05-24 |
| [ADR-0015](ADR-0015-feature-flag-strategy.md)                              | Feature Flag Strategy                                                                    | Accepted   | 2026-05-25 |
| [ADR-0018](ADR-0018-db-encryption-at-rest.md)                              | Database Encryption at Rest                                                              | Accepted   | 2026-05-28 |
| [ADR-0019](ADR-0019-redis-tls-value-encryption.md)                         | Redis TLS and Value Encryption                                                           | Accepted   | 2026-05-28 |
| [ADR-0020](ADR-0020-finops-cost-allocation.md)                             | FinOps: LLM Cost Allocation                                                              | Accepted   | 2026-05-28 |
| [ADR-0022](ADR-0022-testing-strategy.md)                                   | Testing Strategy                                                                         | Accepted   | 2026-05-28 |
| [ADR-0023](ADR-0023-frontend-architecture.md)                              | Frontend Architecture                                                                    | Accepted   | 2026-05-28 |
| [ADR-0024](ADR-0024-api-versioning-strategy.md)                            | API Versioning Strategy                                                                  | Accepted   | 2026-05-28 |
| [ADR-0025](ADR-0025-language-selection.md)                                 | Language Selection for New Services                                                      | Accepted   | 2026-05-24 |
| [ADR-0026](ADR-0026-sox-audit-log-immutability.md)                         | SOX Audit Log Immutability                                                               | Accepted   | 2026-05-31 |
| [ADR-0027](ADR-0027-iso27001-change-management.md)                         | ISO 27001 Change Management                                                              | Accepted   | 2026-05-31 |
| [ADR-0028](ADR-0028-dora-metrics.md)                                       | DORA Metrics                                                                             | Accepted   | 2026-05-31 |
| [ADR-0029](ADR-0029-devsecops-pipeline-security.md)                        | DevSecOps Pipeline Security                                                              | Accepted   | 2026-05-31 |
| [ADR-0030](ADR-0030-rtk-token-efficiency.md)                               | RTK Token Efficiency Integration (removed 2026-06-07; guidance kept in CLAUDE.md §13)    | Deprecated | 2026-06-07 |
| [ADR-0031](ADR-0031-agent-onboarding-protocol.md)                          | Agent Onboarding Protocol                                                                | Accepted   | 2026-06-05 |
| [ADR-0032](ADR-0032-sub-agent-specialization-registry.md)                  | Sub-Agent Specialization Registry                                                        | Accepted   | 2026-06-05 |
| [ADR-0033](ADR-0033-long-running-agent-session-durability.md)              | Long-Running Agent Session Durability                                                    | Accepted   | 2026-06-05 |
| [ADR-0034](ADR-0034-agentic-escalation-protocol.md)                        | Agentic Escalation Protocol                                                              | Accepted   | 2026-06-05 |
| [ADR-0035](ADR-0035-ai-assisted-ci-review.md)                              | AI-Assisted CI Code Review                                                               | Accepted   | 2026-06-05 |
| [ADR-0036](ADR-0036-agentic-cyber-defense.md)                              | Agentic Cyber Defense Automation                                                         | Accepted   | 2026-06-05 |
| [ADR-0037](ADR-0037-governance-gate-enforcement.md)                        | Governance Gate CI Enforcement                                                           | Accepted   | 2026-06-05 |
| [ADR-0038](ADR-0038-learn-stage-feedback-loop.md)                          | Learn Stage Feedback Loop                                                                | Accepted   | 2026-06-05 |
| [ADR-0039](ADR-0039-governed-tool-registry.md)                             | Governed Tool Registry                                                                   | Accepted   | 2026-06-05 |
| [ADR-0040](ADR-0040-agentic-maturity-model.md)                             | Agentic Maturity Self-Assessment                                                         | Accepted   | 2026-06-05 |
| [ADR-0041](ADR-0041-context-graph-autonomy-tier.md)                        | Context Graph — Autonomy Tier                                                            | Accepted   | 2026-06-05 |
| [ADR-0042](ADR-0042-kubernetes-probe-strategy.md)                          | Kubernetes Probe Strategy                                                                | Accepted   | 2026-06-05 |
| [ADR-0043](ADR-0043-otel-collector-pii-redaction-tail-sampling.md)         | OTel Collector OTTL PII Redaction + Tail Sampling                                        | Accepted   | 2026-06-06 |
| [ADR-0044](ADR-0044-otel-agent-span-hierarchy.md)                          | OTel Agent Span Hierarchy                                                                | Accepted   | 2026-06-06 |
| [ADR-0045](ADR-0045-genai-semantic-conventions.md)                         | GenAI Semantic Conventions for LLM                                                       | Accepted   | 2026-06-06 |
| [ADR-0046](ADR-0046-hitl-trace-linking-guardrail-events.md)                | HITL Trace Linking + Guardrail Events                                                    | Accepted   | 2026-06-06 |
| [ADR-0047](ADR-0047-spec-contract-enforcement.md)                          | Spec Contract Enforcement at Runtime                                                     | Accepted   | 2026-06-06 |
| [ADR-0048](ADR-0048-zero-trust-tool-registry.md)                           | Zero-Trust Tool Registry & Operator Authentication                                       | Accepted   | 2026-06-06 |
| [ADR-0049](ADR-0049-runtime-behavioral-monitoring.md)                      | Runtime Behavioral Monitoring                                                            | Accepted   | 2026-06-06 |
| [ADR-0050](ADR-0050-adversarial-abuse-testing.md)                          | Adversarial Abuse Testing Strategy                                                       | Accepted   | 2026-06-06 |
| [ADR-0051](ADR-0051-model-behavioral-contracts.md)                         | Model Behavioral Contracts                                                               | Accepted   | 2026-06-06 |
| [ADR-0052](ADR-0052-agentic-sdlc-e2e-workflow.md)                          | Agentic SDLC E2E Workflow                                                                | Accepted   | 2026-06-06 |
| [ADR-0053](ADR-0053-runtime-correctness-hitl-autonomy-tool-enforcement.md) | Runtime Correctness: HITL/Autonomy/Tool Enforcement                                      | Accepted   | 2026-06-06 |
| [ADR-0054](ADR-0054-machine-readable-governance-contracts.md)              | Machine-Readable Governance Contracts                                                    | Accepted   | 2026-06-06 |
| [ADR-0055](ADR-0055-hotl-operationalization.md)                            | HOTL Operationalization (monitor/override/compensation)                                  | Accepted   | 2026-06-06 |
| [ADR-0056](ADR-0056-release-hardening.md)                                  | Release Hardening (CAB gate / DORA / artifact integrity)                                 | Accepted   | 2026-06-06 |
| [ADR-0057](ADR-0057-repository-hygiene.md)                                 | Repository Hygiene (version SoT / refs / context graph)                                  | Accepted   | 2026-06-06 |
| [ADR-0058](ADR-0058-agentic-spec-driven-delivery-workflow.md)              | Agentic Spec-Driven Delivery (Phase 0 Intake + AI Safety phase)                          | Accepted   | 2026-06-06 |
| [ADR-0059](ADR-0059-reusability-uplift.md)                                 | Reusability Uplift (progressive adoption UX)                                             | Accepted   | 2026-06-06 |
| [ADR-0060](ADR-0060-task-atomicity-skill-budget.md)                        | Task Atomicity & the 2-Skill Budget (decomposition oracle)                               | Accepted   | 2026-06-07 |
| [ADR-0061](ADR-0061-control-binding-ci-gate.md)                            | Control-binding obligations enforced as a CI governance gate                             | Accepted   | 2026-06-07 |
| [ADR-0062](ADR-0062-aurora-postgresql-platform-rdbms.md)                   | Aurora PostgreSQL as the platform RDBMS (vs RDS Multi-AZ + read replicas)                | Accepted   | 2026-06-09 |
| [ADR-0063](ADR-0063-brownfield-terraform-reconciliation.md)                | Brownfield Terraform reconciliation (extend existing modules, do not fork)               | Accepted   | 2026-06-09 |
| [ADR-0064](ADR-0064-delivery-right-sizing-tiers.md)                        | Delivery Right-Sizing / Phase Applicability Tiers + auto-escalation safety valve         | Accepted   | 2026-06-09 |
| [ADR-0065](ADR-0065-test-integrity-invariants.md)                          | Test-Integrity Invariants (RED-first, co-location, no silent count drop, no weakening)   | Accepted   | 2026-06-09 |
| [ADR-0066](ADR-0066-spec-lgs-001-runtime-stack-java-spring-boot.md)        | SPEC-LGS-001 runtime stack: Java 21 / Spring Boot (override of NFR-02 under ADR-0025)    | Accepted   | 2026-06-11 |
| [ADR-0067](ADR-0067-redis-as-timeseries-store.md)                          | Redis as the time-series store for golden-signals (retention; InfluxDB/TimescaleDB exit) | Accepted   | 2026-06-11 |
| [ADR-0068](ADR-0068-golden-signal-extraction-rules.md)                     | Golden-Signal extraction rules (saturation proxy, window semantics, key grammar)         | Accepted   | 2026-06-11 |
| [ADR-0069](ADR-0069-queue-implementation.md)                               | golden-signals queue: in-JVM bounded virtual-thread queue (honours ADR-0003)             | Accepted   | 2026-06-11 |
| [ADR-0070](ADR-0070-governance-gate-enforcement-lifecycle.md)              | Governance gate enforcement lifecycle (report-mode → blocking after burn-in)             | Accepted   | 2026-06-12 |
| [ADR-0071](ADR-0071-repository-settings-as-code.md)                        | Repository settings as code (branch protection codified + drift-checked)                 | Accepted   | 2026-06-12 |
| [ADR-0072](ADR-0072-versioned-security-control-matrices.md)                | Versioned security control matrices (OWASP ASVS v5.0.0 + GenAI/LLM)                      | Accepted   | 2026-06-12 |
| [ADR-0073](ADR-0073-slo-driven-canary-thresholds.md)                       | SLO-driven canary thresholds (per-service config, no hard-coded gates)                   | Accepted   | 2026-06-12 |
| [ADR-0074](ADR-0074-automated-dependency-digest-policy.md)                 | Automated dependency & digest update policy (Renovate)                                   | Accepted   | 2026-06-12 |
| [ADR-0075](ADR-0075-resilience-fallback-policy.md)                         | Resilience fallback policy (degrade-open vs fail-closed)                                 | Accepted   | 2026-06-13 |
| [ADR-0076](ADR-0076-api-structured-error-model-and-correlation.md)         | Structured API error model (problem+json flavour) + X-Request-ID correlation             | Accepted   | 2026-06-14 |
| [ADR-0077](ADR-0077-api-idempotency-keys.md)                               | Idempotency keys for write endpoints (Idempotency-Key header, degrade-open store)        | Accepted   | 2026-06-14 |
| [ADR-0078](ADR-0078-api-pagination-standard.md)                            | List-endpoint pagination standard (offset/limit + X-Total-Count/Link headers)            | Accepted   | 2026-06-14 |
| [ADR-0079](ADR-0079-prompt-externalization-and-no-inline-prompt-gate.md)   | Prompt externalisation (evaluator + orchestrator base) + no-inline-prompt CI gate        | Accepted   | 2026-06-15 |
| [ADR-0080](ADR-0080-groundedness-scoring-as-an-sli.md)                     | Groundedness scoring as an SLI (model-contract test + OTel metric, not a 5th eval dim)   | Accepted   | 2026-06-15 |
| [ADR-0081](ADR-0081-rag-reference-pipeline.md)                             | RAG reference pipeline (chunk→embed→retrieve→rerank→cite→eval; opt-in; controls)         | Accepted   | 2026-06-15 |
| [ADR-0082](ADR-0082-backup-rpo-rto-and-restore-drill-verification.md)      | Consolidated backup RPO/RTO + scheduled, evidenced restore-drill verification            | Accepted   | 2026-06-15 |
| [ADR-0083](ADR-0083-frontend-app-directory-rename.md)                      | Rename `frontend/frontend` → `frontend/web` (refines ADR-0023 path; pattern unchanged)   | Accepted   | 2026-06-15 |

### AI Agents Module _(opt-in)_

These ADRs are **only binding when the AI Agents Module is enabled** (i.e., `src/agents/` is present in your project).
See `docs/optional-extensions/ai-agents/README.md` for the activation checklist.

| ADR                                                    | Title                           | Status   | Date       |
| ------------------------------------------------------ | ------------------------------- | -------- | ---------- |
| [ADR-0010](ADR-0010-agent-framework-selection.md)      | Agent Framework Selection       | Accepted | 2026-05-24 |
| [ADR-0011](ADR-0011-hitl-hotl-model.md)                | HITL/HOTL Human Oversight Model | Accepted | 2026-05-24 |
| [ADR-0014](ADR-0014-multi-agent-harness-strategy.md)   | Multi-Agent Harness Strategy    | Accepted | 2026-05-24 |
| [ADR-0016](ADR-0016-agent-sandbox-execution-policy.md) | Agent Sandbox Execution Policy  | Accepted | 2026-05-25 |
| [ADR-0017](ADR-0017-agent-memory-architecture.md)      | Agent Memory Architecture       | Accepted | 2026-05-27 |
| [ADR-0021](ADR-0021-agent-communication-protocol.md)   | Agent Communication Protocol    | Accepted | 2026-05-28 |
