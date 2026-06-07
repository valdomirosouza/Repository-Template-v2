# Ideal Monorepo Structure — Enterprise Systems

> **Template version:** 1.17.3
> **Last updated:** 2026-05-29
> **Scope:** Generic enterprise monorepo template; AI/agent capabilities are an optional opt-in extension

---

## Executive Summary

This document defines the ideal monorepo structure for **enterprise-grade systems** — including standard microservice backends, event-driven platforms, and optionally systems that incorporate Agentic AI, autonomous agents, LLM-based pipelines, and human-in-the-loop workflows.

The template covers all dimensions of a modern, scalable, reliable, and secure software product:

| Dimension                | Coverage                                                                                                   |
| ------------------------ | ---------------------------------------------------------------------------------------------------------- |
| **Governance**           | ADRs, Specs (SDD), Rules, CLAUDE.md, CONTRIBUTING.md                                                       |
| **Documentation**        | README, CHANGELOG, Glossary, Repo Structure, Dependency Manifest                                           |
| **Change Management**    | RFC lifecycle, CAB process, deploy scripts, rollback procedures                                            |
| **DevSecOps Compliance** | OWASP (Web + LLM Top 10), SAST, DAST, SBOM, Supply Chain, SLSA                                             |
| **SDLC**                 | Full lifecycle: requirements → design → implement → test → release → operate                               |
| **DevOps / CI/CD**       | Pipeline stages, quality gates, canary deploy, blue-green, feature flags                                   |
| **Test Coverage**        | Unit, integration, contract, E2E, performance, security, chaos engineering                                 |
| **SRE Journey**          | Logs, Metrics (Golden Signals), Traces, SLO/SLI, Error Budget, PRR, CUJ                                    |
| **AI Governance**        | EU AI Act, NIST AI RMF, HITL/HOTL controls, audit trail, bias auditing                                     |
| **Data Privacy**         | PII inventory, masking, LGPD (Brazil), GDPR (EU), DPIA/RIPD, data retention                                |
| **Async APIs**           | AsyncAPI 2.6, event-driven architecture, Kafka, gRPC for high performance                                  |
| **Scalability**          | Horizontal (HPA, partitioning, stateless), vertical (VPA, LLM throttling)                                  |
| **Reliability**          | Circuit breaker, PodDisruptionBudget, multi-AZ, graceful shutdown                                          |
| **Chaos Engineering**    | Controlled failure injection, game days, resilience validation in staging (Litmus / Chaos Toolkit)         |
| **Feature Flags**        | Progressive delivery, A/B testing, autonomous-mode toggles, safe LLM model rollouts                        |
| **FinOps**               | LLM token cost attribution, infrastructure cost per SLO met, budget alerts, cost-per-agent-action tracking |

> **AI & Agentic AI (opt-in):** If your project includes AI-governed components — LLM pipelines,
> autonomous agents, multi-agent orchestration, or any system with delegated decision-making — enable
> the AI Agents extension (see `docs/optional-extensions/ai-agents/README.md`). All AI components must
> comply with the AI Governance pillar (Section 9) and its associated ADRs, specs, guardrails, and HITL/HOTL controls.

> **Privacy note:** Any system that processes personal data — regardless of volume — must
> comply with the Data Privacy pillar (Section 10). This includes LGPD obligations for Brazilian data subjects,
> GDPR obligations for EU data subjects, and DPIA/RIPD completion before any production release that handles
> real personal data. When AI agents are enabled, PII masking before LLM ingestion is also mandatory.

---

## Repository Structure

```
<project-name>/                          ← Monorepo root
│
├── ── GOVERNANCE & CONTRACT ──────────────────────────────────────────
│
├── CLAUDE.md                            ← Behavioral contract for Claude Code
├── README.md                            ← Project entry point
├── CHANGELOG.md                         ← Keep-a-Changelog + SemVer
├── SECURITY.md                          ← Vulnerability disclosure policy
├── PRIVACY.md                           ← Data processing notice (LGPD / GDPR)
├── CONTRIBUTING.md                      ← Contribution guide
├── CODE_OF_CONDUCT.md                   ← Code of conduct
├── MONOREPO-STRUCTURE-EN.md            ← This document — enterprise template reference
├── version.txt                          ← Canonical version (single source of truth)
│
├── ── ARCHITECTURE & DECISIONS ───────────────────────────────────────
│
├── docs/
│   ├── adr/                             ← Architecture Decision Records
│   │   ├── README.md                    ← ADR template + master index
│   │   ├── ADR-0001-<title>.md          ← First foundational ADR
│   │   ├── ADR-0002-<title>.md
│   │   ├── ADR-0003-async-api-strategy.md        ← AsyncAPI / event-driven
│   │   ├── ADR-0004-observability-stack.md       ← OTel + Prometheus + Grafana
│   │   ├── ADR-0005-message-broker-selection.md  ← Kafka vs NATS vs RabbitMQ
│   │   ├── ADR-0006-deployment-strategy.md       ← Canary + Blue-Green
│   │   ├── ADR-0007-service-mesh.md              ← Istio vs Linkerd
│   │   ├── ADR-0008-secrets-management.md        ← Vault / AWS Secrets Manager
│   │   ├── ADR-0009-caching-strategy.md          ← Redis + CDN layers
│   │   ├── ADR-0010-agent-framework-selection.md ← Agentic AI: framework choice
│   │   ├── ADR-0011-hitl-hotl-model.md           ← Human oversight model
│   │   ├── ADR-0012-pii-masking-strategy.md      ← Privacy: PII before LLM
│   │   ├── ADR-0013-data-retention-policy.md     ← Privacy: LGPD/GDPR retention
│   │   └── ADR-NNNN-<title>.md                   ← Additional ADRs as needed
│   │
│   ├── api/                             ← API specifications
│   │   ├── openapi/
│   │   │   └── v1/
│   │   │       └── openapi.yaml         ← OpenAPI 3.1 — synchronous REST APIs
│   │   ├── asyncapi/
│   │   │   ├── v1/
│   │   │   │   └── asyncapi.yaml        ← AsyncAPI 2.6 — events / queues
│   │   │   └── v2/
│   │   │       └── migration-guide.md   ← v1→v2 migration guide
│   │   └── grpc/
│   │       └── proto/                  ← Protobuf (inter-service, high throughput)
│   │           └── ai_service.proto     ← AI service gRPC contract
│   │
│   ├── runbooks/                        ← Operational runbooks
│   │   ├── README.md                    ← Runbook template + index
│   │   ├── RB-003-hitl-recovery.md      ← HITL queue recovery procedure
│   │   ├── rollback-procedure.md        ← Detailed rollback playbook
│   │   └── disaster-recovery.md        ← DR Playbook
│   │
│   ├── postmortems/                     ← Historical post-mortems
│   │   ├── README.md                    ← Post-mortem template (blameless)
│   │   └── YYYY-MM-DD-<incident-name>.md
│   │
│   ├── security/
│   │   └── pentest-reports/            ← DAST / pentest reports (placeholder)
│   │
│   ├── privacy/                         ← Data privacy documentation
│   │   ├── dpia/                        ← Data Protection Impact Assessment (GDPR)
│   │   │   └── dpia-v1.md
│   │   ├── ripd/                        ← Relatório de Impacto (LGPD)
│   │   │   └── ripd-v1.md
│   │   ├── pii-inventory.md             ← PII fields catalog + classification
│   │   ├── data-retention-policy.md     ← Retention rules per data type
│   │   └── data-processing-register.md ← Register of Processing Activities (RoPA)
│   │
│   ├── ai-governance/                   ← AI-specific governance artifacts
│   │   ├── README.md                    ← AI governance overview
│   │   ├── model-card.md                ← Model Card (Google / Hugging Face format)
│   │   ├── eu-ai-act-compliance.md      ← EU AI Act Arts. 9, 12–14 checklist
│   │   ├── nist-ai-rmf.md              ← NIST AI RMF mapping
│   │   └── autonomy-boundaries.md      ← HITL / HOTL boundary definitions
│   │
│   ├── sre/
│   │   ├── slo/
│   │   │   ├── slo.yaml                 ← SLO / SLI definitions (YAML)
│   │   │   └── error-budget-policy.md   ← Error budget policy
│   │   ├── prr/
│   │   │   ├── PRR-TEMPLATE.md          ← Production Readiness Review template
│   │   │   └── prr-checklist.yaml       ← Executable PRR checklist
│   │   └── cuj/
│   │       ├── CUJ-001-<name>.md        ← Critical User Journey 1
│   │       ├── CUJ-002-<name>.md
│   │       └── CUJ-NNN-<name>.md
│   │
│   ├── change-management/               ← ITIL-aligned Change Management
│   │   ├── README.md                    ← Full change management process
│   │   ├── RFC-TEMPLATE.md              ← Request for Change template
│   │   ├── CAB-PROCESS.md               ← Change Advisory Board process
│   │   └── rfc/
│   │       └── RFC-NNNN-<title>.md      ← Archived RFCs
│   │
│   ├── quickstart/                      ← Role-specific onboarding guides
│   │   ├── README.md                    ← Guide index
│   │   ├── python-backend.md            ← Python / FastAPI quickstart
│   │   ├── java-backend.md              ← Java / Spring Boot quickstart
│   │   ├── go-backend.md                ← Go quickstart
│   │   ├── frontend.md                  ← Next.js quickstart
│   │   ├── jobs-worker.md               ← Batch / scheduled jobs quickstart
│   │   ├── add-new-service.md           ← 10-step new service checklist
│   │   ├── contract-driven-dev.md       ← Generate code from OpenAPI / AsyncAPI / proto
│   │   ├── local-dev-setup.md           ← Local dev environment guide
│   │   ├── hybrid-workflow.md           ← Vibe → Agentic hybrid workflow guide
│   │   ├── vibe-to-agentic.md           ← Progressive autonomy onboarding
│   │   └── ai-agents.md                 ← AI Agents extension activation guide
│   │
│   ├── compliance/                      ← Security & compliance documentation
│   │   ├── README.md                    ← Compliance package overview
│   │   ├── hardening-plan.md            ← Security hardening programme
│   │   ├── remediation-register.md      ← Open control gaps + resolution tracking
│   │   ├── iso27001-annex-a-control-matrix.md ← ISO 27001 control mapping
│   │   ├── soc2-tsc-mapping.md          ← SOC 2 Trust Services Criteria mapping
│   │   ├── slsa-supply-chain-assessment.md    ← SLSA supply chain assessment
│   │   ├── security-questionnaire-quickref.md ← Vendor security questionnaire answers
│   │   └── trust-summary.md             ← One-page trust summary for customers
│   │
│   ├── governance/                      ← Team governance documentation
│   │   └── owner-onboarding.md          ← New maintainer / team onboarding guide
│   │
│   ├── optional-extensions/
│   │   └── ai-agents/
│   │       └── README.md                ← AI Agents Module activation / removal guide
│   │
│   ├── dependency-manifest.yaml         ← Layer 2: enriched dependency manifest
│   ├── glossary.md                      ← Canonical glossary
│   └── repo-structure.md               ← Annotated directory tree
│
├── ── SPECS — SPEC-DRIVEN DEVELOPMENT (SDD) ──────────────────────────
│
├── specs/
│   ├── README.md                        ← Spec hierarchy + ownership table
│   │
│   ├── system/
│   │   ├── vision.md                    ← Product vision and goals
│   │   ├── architecture.md              ← High-level architecture
│   │   ├── async-event-flow.md          ← Async event flow design
│   │   └── request-pipeline.md         ← End-to-end request pipeline spec
│   │
│   ├── sdlc/
│   │   └── development-lifecycle.md    ← Full SDLC lifecycle (5 stages + gate criteria)
│   │
│   ├── observability/
│   │   ├── agent-performance.md         ← Agent performance observability spec
│   │   └── agent-supervision.md        ← Agent supervision dashboard spec
│   │
│   ├── api/
│   │   └── async-api-design.md          ← Async API patterns (events, queues)
│   │
│   ├── security/
│   │   ├── threat-model.md              ← Threat model (STRIDE)
│   │   ├── pentest-checklist.md         ← Penetration testing checklist
│   │   └── rbac-model.md               ← Role-based access control model
│   │
│   ├── ai/                              ← AI-specific specs (opt-in)
│   │   ├── README.md                    ← AI specs index
│   │   ├── agent-design.md              ← Agent architecture (Perception→Reason→Act)
│   │   ├── agent-memory.md              ← Agent memory architecture spec
│   │   ├── autonomous-mode-levels.md    ← Autonomy levels (NONE→LOW→MEDIUM→FULL)
│   │   ├── feedback-loop.md             ← Agent feedback loop spec
│   │   ├── guardrails.md                ← Technical guardrails spec
│   │   ├── harness-design.md            ← Multi-agent harness spec (Planner→Generator→Evaluator)
│   │   ├── hitl-hotl.md                 ← Human oversight model spec
│   │   ├── hitl-notification.md         ← HITL notification and escalation spec
│   │   └── sandbox-execution.md        ← Agent sandbox execution policy
│   │
│   ├── privacy/
│   │   ├── pii-inventory.md             ← PII fields + classification
│   │   ├── data-retention.md            ← Retention rules + LGPD/GDPR alignment
│   │   ├── dpia-ripd.md                 ← DPIA (GDPR) / RIPD (LGPD) spec
│   │   ├── db-encryption-at-rest.md     ← AES-256-GCM encryption spec (ADR-0018)
│   │   └── redis-tls.md                ← Redis TLS + value encryption spec (ADR-0019)
│   │
│   └── ethics/
│       └── ethical-ai-principles.md    ← 6 AI ethics principles (EU AI Act + LGPD Art. 20)
│
├── ── SOURCE CODE ─────────────────────────────────────────────────────
│
├── src/
│   │
│   ├── agents/                          ← AI / Agentic AI components
│   │   ├── <agent-name>/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                 ← Agent core (Perception → Reason → Act)
│   │   │   ├── tools.py                 ← Agent tools (external integrations)
│   │   │   └── prompts.py              ← LLM prompt templates
│   │   ├── orchestrator/
│   │   │   ├── orchestrator.py          ← Perception→Reason→Act loop; HITL routing via feature flag
│   │   │   └── router.py               ← Task routing between agents
│   │   ├── harness/                     ← Multi-agent harness (ADR-0014)
│   │   │   ├── coordinator.py           ← HarnessCoordinator (solo/simplified/full modes)
│   │   │   ├── planner.py               ← PlannerAgent — sprint contract generation
│   │   │   ├── evaluator.py             ← EvaluatorAgent — skepticism scoring (4 dimensions)
│   │   │   ├── context_manager.py       ← ContextManager — snapshot + reset logic
│   │   │   └── models.py               ← TaskBrief, SprintContract, EvaluatorScore, HarnessResult
│   │   ├── hitl_gateway.py             ← HITL Gateway — mandatory human approval (ADR-0011)
│   │   └── hitl_store.py               ← HITLStore Protocol + InMemoryHITLStore + HITLRedisStore
│   │
│   ├── api/
│   │   ├── rest/                        ← FastAPI / Express — synchronous APIs
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── <domain>.py
│   │   │   │   └── health.py
│   │   │   └── middleware/
│   │   │       ├── auth.py
│   │   │       ├── rate_limiter.py
│   │   │       └── tracing.py
│   │   │
│   │   ├── async/                       ← Async APIs (event-driven)
│   │   │   ├── consumers/
│   │   │   │   └── <domain>_consumer.py ← Kafka / NATS consumer
│   │   │   ├── producers/
│   │   │   │   └── <domain>_producer.py ← Kafka / NATS producer
│   │   │   └── schemas/                 ← Event schemas (Pydantic / Avro)
│   │   │       └── <domain>_events.py
│   │   │
│   │   └── grpc/                        ← gRPC — high-performance inter-service
│   │       ├── server.py
│   │       └── generated/              ← Auto-generated from proto/
│   │
│   ├── memory/                          ← Agent memory (RAG + Vector DB)
│   │   ├── vector_store.py              ← Weaviate / Pinecone / pgvector
│   │   └── document_indexer.py         ← Index runbooks, policies, history
│   │
│   ├── guardrails/                      ← Technical safety guardrails
│   │   ├── action_limits.py             ← Agent action rate limits + scope limits
│   │   ├── pii_filter.py                ← PII masking before LLM ingestion
│   │   ├── prompt_injection_guard.py    ← OWASP LLM01 — Prompt Injection defense
│   │   └── audit_logger.py             ← Immutable audit log of all agent actions
│   │
│   ├── observability/                   ← Observability instrumentation
│   │   ├── otel_setup.py                ← OpenTelemetry SDK bootstrap + distributed tracing
│   │   ├── metrics.py                   ← Prometheus metrics (Golden Signals + agent metrics)
│   │   └── logger.py                   ← Structured JSON logging
│   │
│   └── shared/                          ← Shared code across modules
│       ├── config.py                    ← Config via env vars (Pydantic Settings)
│       ├── models.py                    ← Domain models (AuditEvent, AgentActionRequest, etc.)
│       ├── retry.py                     ← with_retry() + CircuitBreaker (CLOSED/OPEN/HALF_OPEN)
│       ├── db_client.py                 ← ResilientDBPool (asyncpg + CB + retry + timeout)
│       ├── db_encryption.py             ← AES-256-GCM EncryptedField (ADR-0018)
│       ├── broker.py                    ← Kafka / InMemoryBroker abstraction
│       ├── llm_client.py                ← LLMClient Protocol + TimeoutLLMClientWrapper
│       └── feature_flags.py            ← is_autonomous_mode_enabled() — OpenFeature SDK (ADR-0015)
│
├── ── POLYGLOT SERVICES ───────────────────────────────────────────────
│
├── services/
│   ├── domain-service/                  ← Java 21 / Spring Boot 3.3 — CRUD API + Kafka consumer
│   │   └── README.md
│   └── event-worker/                    ← Go 1.23 — stateless high-throughput Kafka consumer
│       └── README.md
│
├── frontend/
│   └── frontend/                        ← Next.js 14 / TypeScript — HITL operator approval UI
│       └── README.md
│
├── scaffold/                            ← Code generation templates + scaffolding CLI
│   ├── scaffold.py                      ← make new-service entry point
│   └── templates/
│       ├── python/                      ← Python service template
│       ├── java/                        ← Java service template
│       └── go/                          ← Go service template
│
├── ── TESTS ───────────────────────────────────────────────────────────
│
├── tests/
│   ├── README.md                        ← Testing strategy + pyramid rationale
│   ├── conftest.py                      ← Global fixtures (pytest)
│   │
│   ├── unit/                            ← Unit tests — coverage ≥ 80%
│   │   ├── agents/
│   │   │   └── test_<agent>.py
│   │   ├── guardrails/
│   │   │   ├── test_pii_filter.py
│   │   │   └── test_prompt_injection_guard.py
│   │   └── api/
│   │       └── test_<router>.py
│   │
│   ├── integration/                     ← Integration — real services or mocks
│   │   ├── test_<broker>_consumer.py
│   │   ├── test_vector_store.py
│   │   └── test_hitl_gateway.py
│   │
│   ├── e2e/                             ← End-to-end — full user flow
│   │   ├── test_<flow>_lifecycle.py
│   │   └── test_hitl_approval_flow.py
│   │
│   ├── contract/                        ← Consumer-driven contract tests
│   │   ├── pacts/                       ← Pact contract files
│   │   └── test_api_contracts.py
│   │
│   ├── performance/                     ← Load and performance tests
│   │   ├── k6/
│   │   │   ├── request-api-load.js      ← k6 load test for POST /v1/requests
│   │   │   └── hitl-decision-load.js    ← k6 load test for HITL decision endpoint
│   │   └── benchmarks/
│   │       └── test_orchestrator_benchmarks.py
│   │
│   ├── security/                        ← Security-focused tests
│   │   ├── test_owasp_web_top10.py
│   │   ├── test_owasp_llm_top10.py      ← LLM01–LLM10 automated checks
│   │   ├── test_prompt_injection.py
│   │   ├── test_pii_leakage.py          ← Verify no PII leaks in logs / LLM calls
│   │   └── test_auth_controls.py
│   │
│   ├── chaos/                           ← Chaos Engineering
│   │   ├── experiments/
│   │   │   ├── kill-agent.yaml
│   │   │   ├── network-partition.yaml
│   │   │   ├── broker-outage.yaml
│   │   │   ├── agent-context-overflow.yaml
│   │   │   ├── evaluator-disagreement.yaml
│   │   │   ├── hitl-store-degradation.yaml
│   │   │   ├── llm-api-timeout.yaml
│   │   │   └── prompt-injection-under-load.yaml
│   │   └── runbooks/
│   │       └── game-day-playbook.md
│   │
│   └── fixtures/                        ← Test data fixtures (realistic, PII-free)
│       └── <domain>/
│           └── <scenario>.json
│
├── ── INFRASTRUCTURE (IaC) ────────────────────────────────────────────
│
├── infrastructure/
│   ├── README.md
│   │
│   ├── terraform/                       ← Infrastructure as Code
│   │   ├── modules/
│   │   │   ├── kubernetes/
│   │   │   ├── message-broker/          ← Kafka / NATS / RabbitMQ
│   │   │   ├── cache/                   ← Redis
│   │   │   ├── vector-db/               ← pgvector / Weaviate / Pinecone
│   │   │   ├── observability/           ← Prometheus + Grafana + Jaeger stack
│   │   │   └── networking/
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   │   └── main.tf
│   │   │   ├── staging/
│   │   │   │   └── main.tf
│   │   │   └── production/
│   │   │       └── main.tf
│   │   └── backend.tf                  ← Remote state (S3 + DynamoDB lock)
│   │
│   ├── helm/                            ← Kubernetes deployments
│   │   ├── <service-name>/
│   │   │   ├── Chart.yaml
│   │   │   ├── values.yaml
│   │   │   ├── values-staging.yaml
│   │   │   ├── values-production.yaml
│   │   │   └── templates/
│   │   │       ├── deployment.yaml
│   │   │       ├── service.yaml
│   │   │       ├── hpa.yaml             ← HorizontalPodAutoscaler (scale-out)
│   │   │       ├── vpa.yaml             ← VerticalPodAutoscaler (scale-up)
│   │   │       ├── pdb.yaml             ← PodDisruptionBudget (reliability)
│   │   │       └── servicemonitor.yaml  ← Prometheus ServiceMonitor
│   │   └── message-broker/
│   │       └── values.yaml
│   │
│   ├── k8s/                             ← Static Kubernetes manifests
│   │   └── network-policies/            ← NetworkPolicy definitions + README
│   │
│   ├── monitoring/                      ← Observability configuration
│   │   ├── prometheus/
│   │   │   └── rules/
│   │   │       ├── golden-signals.yaml  ← Alerting: Traffic, Error, Saturation, Latency
│   │   │       └── agent-alerts.yaml    ← 14 agent-specific alert rules
│   │   ├── grafana/
│   │   │   ├── dashboards/              ← 5 pre-provisioned dashboards
│   │   │   │   ├── golden-signals.json
│   │   │   │   ├── sre-overview.json
│   │   │   │   ├── agent-performance.json
│   │   │   │   └── cuj-dashboards/      ← One dashboard per Critical User Journey
│   │   │   └── datasources/             ← Auto-provisioned Prometheus datasource
│   │   └── jaeger/
│   │       └── sampling-strategies.json ← Per-service trace sampling policy
│   │
│   ├── message-broker/                  ← Broker configuration
│   │   ├── topics/
│   │   │   ├── domain-events.yaml       ← Topic definitions
│   │   │   └── agent-events.yaml
│   │   └── schema-registry/
│   │       └── avro/                   ← Avro schemas for events
│   │
│   ├── feature-flags/                   ← Feature flag configuration
│   │   ├── README.md
│   │   └── flags/
│   │       ├── autonomous-mode.yaml     ← Enable/disable agent autonomy
│   │       ├── new-model.yaml           ← Gradually roll out new LLM model
│   │       └── <feature>.yaml
│   │
│   └── scripts/
│       ├── deploy/
│       │   ├── deploy.sh               ← Deploy script (canary / blue-green / rolling)
│       │   ├── rollback.sh             ← Automated rollback script
│       │   ├── smoke-test.sh           ← Post-deploy smoke tests
│       │   └── health-check.sh         ← Service health verification
│       └── db/
│           ├── migrate.sh
│           └── seed-fixtures.sh
│
├── ── CI/CD & HARNESS ─────────────────────────────────────────────────
│
├── harness/
│   ├── code-check.yml                   ← PR gate: lint + unit + SAST + secrets
│   ├── staging-check.yml                ← Staging: integration + DAST + perf
│   ├── release-check.yml                ← Release: SBOM + signing + gate
│   └── doc-check.yml                   ← Doc gate: ADR + spec + changelog
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                       ← Python CI: governance → lint → unit → integration → security
│   │   ├── ci-java.yml                  ← Java CI: Checkstyle → SpotBugs → OWASP → JaCoCo
│   │   ├── ci-go.yml                    ← Go CI: go mod tidy → golangci-lint → race detector
│   │   ├── ci-frontend.yml              ← Frontend CI: ESLint → TS check → Jest → Playwright
│   │   ├── cd-staging.yml               ← CD staging: build → push → Helm deploy → smoke tests
│   │   ├── cd-production.yml            ← CD prod: canary 5%→25%→100% + auto-rollback
│   │   ├── pr-governance.yml            ← PR governance: conventional title, changelog, spec ref
│   │   ├── codeql.yml                   ← GitHub CodeQL SAST
│   │   ├── secret-scanning.yml          ← detect-secrets + custom patterns
│   │   ├── sbom.yml                     ← SBOM generation + Cosign signing
│   │   ├── release.yml                  ← Release automation
│   │   ├── chaos-schedule.yml           ← Scheduled chaos experiments
│   │   ├── auto-merge.yml               ← Auto-merge for bot PRs
│   │   └── index-docs.yml              ← Documentation indexing
│   │
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md                ← Bug report (includes spec reference + DoD)
│   │   └── change_request.md            ← RFC / Change Request template
│   │
│   ├── pull_request_template.md         ← PR template (includes workflow compliance checklist)
│   ├── dependabot.yml                   ← Dependabot auto-update config
│   └── CODEOWNERS                      ← @your-org/* team handles by directory
│
├── ── SKILLS (Claude Code) ────────────────────────────────────────────
│
├── skills/
│   ├── README.md                        ← Enterprise shared skills catalog
│   ├── project-skills-catalog.md        ← Project-specific skills catalog
│   │
│   ├── domain/                          ← Domain skills
│   ├── sdlc/                            ← SDLC skills
│   ├── observability/                   ← Observability skills
│   ├── devsecops/                       ← DevSecOps skills
│   ├── sre/                             ← SRE skills
│   ├── api/                             ← API design skills
│   ├── change-management/               ← Change management skills
│   ├── ai/                              ← Agentic AI skills
│   ├── privacy/                         ← Privacy + PII skills (LGPD / GDPR)
│   ├── ethics/                          ← AI ethics skills
│   └── engineering/                     ← Engineering governance skills
│
├── ── PROJECT CONFIGURATION ───────────────────────────────────────────
│
├── pyproject.toml                       ← Python project config (uv / hatchling)
├── uv.lock                              ← Pinned Python dependencies (uv lock file)
├── alembic.ini                          ← Database migration config
├── mkdocs.yml                           ← Documentation site config (MkDocs Material)
├── .env.example                         ← Environment variables template (all services)
├── .gitignore
├── .pre-commit-config.yaml              ← Pre-commit hooks (ruff, mypy, detect-secrets, bandit)
├── .secrets.baseline                    ← detect-secrets baseline for CI
├── .trivyignore                         ← Trivy CVE ignore list
├── Dockerfile                           ← Multi-stage application container
├── docker-compose.yml                   ← Full local dev stack (9 services)
├── docker-compose.test.yml             ← Integration test stack (offset ports)
├── docker-compose.sandbox.yml           ← Sandbox execution environment
├── Makefile                             ← All make targets (setup, test, lint, deploy, codegen)
│
└── .devcontainer/
    ├── devcontainer.json               ← VSCode / GitHub Codespaces config
    └── Dockerfile                      ← Reproducible dev environment
```

---

## Critical Processes

### 1. Change Management — Issue Registry

Every code change must follow this documented flow:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CHANGE MANAGEMENT FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

1. ISSUE CREATION (GitHub Issue)
   Template: .github/ISSUE_TEMPLATE/change_request.md
   Required fields:
   - Problem description / motivation
   - Referenced spec (specs/*)
   - Change type: Standard | Normal | Emergency
   - Estimated impact (affected services / data flows)
   - Acceptance criteria (Given / When / Then)
   - Rollback plan

2. RFC (Request for Change)
   Required for: Normal and Emergency changes
   - File: docs/change-management/rfc/RFC-NNNN-<title>.md
   - Review: Tech Lead + Security Lead (Normal) | TL async (Emergency)
   - Approval: CAB (Normal) | TL + SecOps async (Emergency)
   - Note: changes affecting PII processing require DPO review

3. BRANCH & PR
   Branch naming:
     feature/SPEC-NNN-<description>
     fix/SPEC-NNN-<description>
     hotfix/SPEC-NNN-<description>
   PR template: .github/pull_request_template.md
   Required fields: Issue #, referenced Spec, impacted ADRs, deploy script

4. CI/CD PIPELINE
   See pipeline detail in Section 2.

5. DEPLOY SCRIPT (infrastructure/scripts/deploy/deploy.sh)
   Parameters:
     --strategy=canary|blue-green|rolling
     --env=staging|production
   Steps:
     a. Pre-deploy health check
     b. Deploy new version
     c. Smoke tests (smoke-test.sh)
     d. Golden Signals monitoring window (15 min for canary)
     e. Auto-rollback if SLO breached

6. POST-DEPLOY TESTS
   - Smoke tests: infrastructure/scripts/deploy/smoke-test.sh
   - Golden Signals check: Traffic, Error, Saturation, Latency
   - CUJ validation: 5-min monitoring of all critical user journeys
   - Privacy check: verify no PII leakage in new log paths

7. ROLLBACK PROCEDURE (infrastructure/scripts/deploy/rollback.sh)
   Automatic triggers:
   - Error rate > SLO threshold (defined in slo.yaml)
   - Latency p99 > SLO target
   - Availability < SLO target
   Manual procedure: docs/runbooks/rollback-procedure.md
   Maximum RTO target: defined per service in slo.yaml

8. CHANGELOG UPDATE (automated via Release Please + manual for context)
   Categories: Added | Changed | Fixed | Security | Removed | Privacy
   Every entry must reference: Issue #, ADR # (if applicable), RFC #

9. POST-DEPLOY MONITORING
   - Standard changes: 24h observation window
   - Infrastructure changes: 72h observation window
   - Changes affecting PII pipelines: DPO sign-off required post-deploy
```

### 2. CI/CD Pipeline — Full Stages

```yaml
# .github/workflows/ci.yml

stages:

  1. VALIDATE  (runs on every PR)
     ├── lint                      # Language-specific (ruff, mypy, eslint)
     ├── type-check
     ├── secret-detection          # gitleaks / TruffleHog — zero secrets = blocker
     ├── dependency-audit          # pip-audit + OWASP Dependency Check
     ├── spec-compliance-check     # Is a spec referenced in this PR?
     ├── IaC-scan                  # Checkov / tfsec
     └── license-check             # FOSSA / license-checker

  2. TEST
     ├── unit-tests                # Coverage ≥ 80% — blocker
     ├── integration-tests         # docker-compose.test.yml
     ├── contract-tests            # Pact / OpenAPI contract
     └── observability-validation  # Log schema, OTel propagation, metric labels

  3. SECURITY
     ├── SAST                      # Semgrep + CodeQL — zero CRITICAL/HIGH = blocker
     ├── SCA                       # Snyk — zero Critical CVEs = blocker
     ├── container-scan            # Trivy (base image CVEs)
     ├── OWASP-LLM-checks          # Prompt injection, data poisoning, excessive agency
     └── PII-leakage-scan          # Verify test fixtures contain no real PII

  4. BUILD
     ├── build-artifact            # Multi-stage Docker build
     ├── sign-artifact             # Cosign / Sigstore (SLSA Level 2+)
     ├── generate-SBOM             # Syft / CycloneDX — signed SBOM
     └── push-to-registry

  5. STAGING DEPLOY
     ├── helm-deploy               # Deploy to staging namespace
     ├── smoke-tests
     ├── DAST                      # OWASP ZAP full scan — zero Top-10 critical = blocker
     └── performance-baseline      # k6 load test vs baseline

  6. PRODUCTION DEPLOY
     requires: [manual-approval, RFC-approved, error-budget > 10%]
     strategy: canary (5% → 25% → 100%)
     ├── golden-signal-monitoring  # 15 min observation per step
     └── auto-rollback             # Triggered on SLO breach at any step
```

#### Quality Gates — All Blocking

| Gate             | Criterion                            | Blocks            |
| ---------------- | ------------------------------------ | ----------------- |
| Lint             | Zero critical rule violations        | Merge             |
| Unit tests       | Coverage ≥ 80%, zero failures        | Merge             |
| SAST             | Zero CRITICAL / HIGH findings        | Merge             |
| Secret detection | Zero secrets detected                | Merge             |
| Container scan   | Zero Critical CVEs in base image     | Merge             |
| SBOM             | Generated and signed                 | Release           |
| DAST             | Zero OWASP Top 10 critical findings  | Staging → Prod    |
| Human review     | Minimum 1 approved reviewer          | Merge             |
| Error budget     | Budget > 10%                         | Production deploy |
| RFC approved     | For Normal / Emergency changes       | Production deploy |
| PII scan         | No real PII in test fixtures or logs | Merge             |

---

### 3. SRE Journey

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SRE JOURNEY                                  │
└─────────────────────────────────────────────────────────────────────┘

GOLDEN SIGNALS  (infrastructure/monitoring/prometheus/rules/golden-signals.yaml)
  │
  ├── TRAFFIC       → requests/s by endpoint, event throughput, agent actions/s
  ├── ERROR RATE    → 4xx/5xx rate, agent error rate, LLM failure rate
  ├── SATURATION    → CPU / Memory / Queue depth / LLM token budget usage
  └── LATENCY       → p50 / p95 / p99 / p999 per endpoint and per CUJ

LOGS  (src/observability/logger.py)
  │
  ├── Format: Structured JSON (OpenTelemetry Log Data Model)
  ├── Required fields: trace_id, span_id, service, severity, message, timestamp
  ├── PII rule: masked BEFORE any log write (guardrails/pii_filter.py)
  │   → Applies to: user IDs, emails, IPs, personal names, free-text fields
  └── Retention: 30d hot / 90d warm / 1 year cold (per LGPD / GDPR policy)

TRACES  (src/observability/otel_setup.py)
  │
  ├── Backend: Jaeger (infrastructure/monitoring/jaeger/)
  ├── Propagation: W3C TraceContext (across sync + async boundaries)
  ├── Required spans: one span per agent action, one per LLM call
  └── Correlation: trace_id injected into every broker message header

METRICS  (src/observability/metrics.py)
  │
  ├── <service>_requests_total          ← Counter: requests by status
  ├── <service>_latency_seconds         ← Histogram: request latency
  ├── agent_actions_total               ← Counter: agent actions by type + result
  ├── hitl_approvals_total              ← Counter: HITL approvals
  ├── hitl_rejections_total             ← Counter: HITL rejections (safety signal)
  └── llm_token_usage_total            ← Counter: tokens consumed (cost proxy)

SLO / SLI / ERROR BUDGET  (docs/sre/slo/slo.yaml)
  │
  ├── Define one SLO file per service
  ├── Burn rate alerts: 1h fast burn (14.4x) + 6h slow burn (6x)
  └── Error budget policy: feature freeze when budget < 10%

PRR — Production Readiness Review  (docs/sre/prr/)
  │
  Mandatory before every production deployment:
  ├── SLO defined and approved (slo.yaml committed)
  ├── All CUJs documented and dashboard-monitored
  ├── Runbook reviewed by someone outside the authoring team
  ├── Golden Signals dashboards validated
  ├── Alerts configured, tested, and routed to on-call
  ├── HITL controls active for all autonomous agent actions in production
  ├── PII masking validated end-to-end (no PII in third-party logs)
  ├── DPIA / RIPD approved (docs/privacy/)
  ├── Threat model current (specs/security/threat-model.md)
  ├── SBOM generated and signed
  └── Error budget > 10%

CUJs — Critical User Journeys  (docs/sre/cuj/)
  │
  Define one CUJ file per critical path. Minimum structure per CUJ:
  ├── User role and goal
  ├── Step-by-step happy path
  ├── SLO target (latency + availability)
  ├── Linked Grafana dashboard (infrastructure/monitoring/grafana/dashboards/cuj-NNN.json)
  └── Failure scenarios and expected degradation behavior
```

---

### 4. Async API Strategy

```
PRINCIPLE: Async-first for high-volume, latency-tolerant flows.
           Sync (REST / gRPC) only for: health checks, HITL approvals,
           direct user-facing queries, and low-latency inter-service calls.

STACK:
  Message Broker:   Apache Kafka (high durability, replay, partitioning)
  Schema Registry:  Confluent Schema Registry (Avro / JSON Schema)
  AsyncAPI 2.6:     docs/api/asyncapi/ (event contract — treated as a first-class API)

EVENT TOPOLOGY PATTERN:
  <domain>.created     → Producer service → Consumer service A
  <domain>.updated     → Producer service → Consumer service B + Audit
  <domain>.completed   → Service chain continues or terminates
  agent.action.proposed → Agent → HITL Gateway → Human approver
  agent.action.approved → HITL Gateway → Agent (executes)
  agent.action.executed → Agent → Audit Log + Notification

GUARANTEES:
  - At-least-once delivery with idempotent consumers (deduplication key per event)
  - Schema evolution: backward / forward compatible (Avro union types)
  - Dead Letter Queue (DLQ) for unprocessable messages
  - Retention: minimum 7 days (allows reprocessing on consumer failure)
  - PII in events: masked at producer side before publish

OBSERVABILITY:
  - Consumer lag ≤ threshold (Golden Signal: Saturation)
  - Trace propagation via W3C TraceContext in broker message headers
  - End-to-end latency: publish timestamp → consumer ack timestamp
```

---

## Section 9 — AI Governance

This section applies to **any system component** that incorporates:

- LLM-based generation or classification
- Autonomous agents (Agentic AI)
- Multi-agent orchestration
- Automated decision-making with real-world effects

### Human Oversight Model

| Layer                          | Mode                         | Description                                                            |
| ------------------------------ | ---------------------------- | ---------------------------------------------------------------------- |
| Monitoring & Classification    | **HOTL** — Human on the Loop | Agent acts autonomously; human monitors with override always available |
| Actions with real-world effect | **HITL** — Human in the Loop | Agent proposes; human must approve before execution                    |

### Guardrails — Mandatory Technical Controls

| Guardrail                        | Implementation                         | OWASP LLM Risk |
| -------------------------------- | -------------------------------------- | -------------- |
| Prompt Injection defense         | `guardrails/prompt_injection_guard.py` | LLM01          |
| PII masking before LLM ingestion | `guardrails/pii_filter.py`             | LLM06          |
| Action scope limits              | `guardrails/action_limits.py`          | LLM08          |
| Immutable audit log              | `guardrails/audit_logger.py`           | LLM09          |

### Compliance Baseline (AI)

| Standard             | Domain                                     | Key Articles / Controls      |
| -------------------- | ------------------------------------------ | ---------------------------- |
| **EU AI Act**        | Human oversight, transparency, audit trail | Arts. 9, 12, 13, 14          |
| **NIST AI RMF**      | AI risk governance, autonomy controls      | Govern, Map, Measure, Manage |
| **OWASP LLM Top 10** | LLM-specific attack surface                | LLM01–LLM10                  |
| **ISO 42001**        | AI management system                       | All clauses                  |

### Model Card (docs/ai-governance/model-card.md)

Required for every LLM or ML model in production. Minimum fields:

```markdown
# Model Card — <Model Name>

## Model Details

- Provider / Version / API endpoint
- Intended use cases
- Out-of-scope uses

## Training Data (if fine-tuned)

- Data sources, date range, known biases

## Performance

- Benchmark results relevant to the use case
- Evaluation methodology

## Ethical Considerations

- Known failure modes
- Bias assessment summary (link to docs/ai-governance/bias-audit.md)
- Autonomy level: HITL / HOTL (link to ADR)

## Privacy

- Data sent to model (fields, classification)
- PII handling: masked / not sent
- Data retention at provider (link to DPA)
```

---

## Section 10 — Data Privacy (PII · LGPD · GDPR)

This section applies to **every component** that processes personal data, including
logs, metrics, traces, event payloads, LLM prompts, agent context, and databases.

### Privacy by Design — Non-Negotiable Rules

1. **PII masking before LLM ingestion** — no personal data enters any LLM API unmasked.
2. **PII masking before logging** — `guardrails/pii_filter.py` runs before every log write.
3. **PII masking before broker publish** — applied at producer side before event is emitted.
4. **Data minimization** — collect only what is strictly necessary for the stated purpose.
5. **Purpose limitation** — data collected for one purpose must not be reused for another.
6. **DPIA / RIPD before production** — any new data processing activity requires impact assessment.

### PII Classification (docs/privacy/pii-inventory.md)

| Class              | Examples                            | Handling                                       |
| ------------------ | ----------------------------------- | ---------------------------------------------- |
| **L1 — Critical**  | CPF, SSN, health data, biometric    | Encrypt at rest + in transit; never in logs    |
| **L2 — Sensitive** | Full name, email, phone, IP address | Mask in logs; pseudonymize for analytics       |
| **L3 — Internal**  | Username, user ID, session token    | Mask in external logs; allow in internal audit |
| **L4 — Public**    | Publicly declared role, org name    | No special handling required                   |

### Regulatory Compliance

| Regulation                 | Jurisdiction   | Key Obligations in this System                                                                                                                   |
| -------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **LGPD** (Lei 13.709/2018) | Brazil         | RIPD before production; ANPD notification of breaches; DPO designation; lawful basis for all processing                                          |
| **GDPR** (EU 2016/679)     | European Union | DPIA before high-risk processing; data subject rights (access, deletion, portability); cross-border transfer mechanisms; 72h breach notification |

### Data Retention Rules (docs/privacy/data-retention-policy.md)

| Data Type               | Retention                  | Deletion Method                      |
| ----------------------- | -------------------------- | ------------------------------------ |
| Logs (containing PII)   | 30 days hot / 90 days warm | Automated purge via retention policy |
| Audit logs (anonymized) | 1 year                     | Archived, then deleted               |
| Agent action history    | 90 days                    | Soft delete + 30d hard delete        |
| User-facing data        | Per product requirement    | User-initiated + automated expiry    |
| Backup data             | 30 days                    | Automated rotation                   |

### DPIA / RIPD Checklist

Before every production release that introduces or changes personal data processing:

```markdown
- [ ] Processing activity described in data-processing-register.md
- [ ] PII fields catalogued in pii-inventory.md
- [ ] Lawful basis identified (consent / legitimate interest / legal obligation)
- [ ] DPIA completed and approved (docs/privacy/dpia/dpia-vN.md) — GDPR Art. 35
- [ ] RIPD completed and approved (docs/privacy/ripd/ripd-vN.md) — LGPD Art. 38
- [ ] DPO review sign-off obtained
- [ ] Data subject rights mechanisms tested (access, deletion, portability)
- [ ] Third-party data processors listed with DPA references
- [ ] LLM providers: confirmed data is not used for training (DPA clause)
- [ ] PII masking validated end-to-end (no PII in third-party logs)
- [ ] Breach notification procedure documented and tested
```

---

## Section 11 — Scalability Architecture

```
HORIZONTAL SCALE-OUT:
  ├── Kubernetes HPA (helm/templates/hpa.yaml)
  │   └── Scaling metric: custom (broker consumer lag + CPU)
  ├── Broker partitioning: by entity type or priority tier
  ├── Stateless services: state externalized to Redis + Vector DB
  └── Load balancer: service mesh (Istio / Linkerd) with circuit breaker

VERTICAL SCALE-UP:
  ├── Kubernetes VPA (helm/templates/vpa.yaml) — Auto mode
  └── LLM: token budget throttle + automatic fallback to smaller model

RELIABILITY PATTERNS:
  ├── Circuit Breaker: tenacity (retry + exponential backoff)
  ├── PodDisruptionBudget: minimum 2 pods available at all times
  ├── Multi-AZ: pod anti-affinity rules enforced in Helm chart
  ├── Graceful shutdown: SIGTERM handler + 30s drain window
  └── Chaos Engineering: weekly game day (tests/chaos/experiments/)

CACHING LAYERS:
  ├── L1 — In-process: LRU cache (functools / node-cache)
  ├── L2 — Distributed: Redis (TTL per data type)
  ├── L3 — Semantic: Vector DB (embeddings for RAG retrieval)
  └── L4 — Edge: CDN for static assets and public API responses
```

---

## Section 12 — Developer Experience (DX)

```
LOCAL SETUP (single command):
  make setup          ← Installs dependencies, sets up .env from .env.example,
                         starts docker-compose stack, runs migrations

DAILY WORKFLOW:
  make test           ← Full test suite (unit + integration)
  make lint           ← Lint + type check + secret scan
  make deploy-staging ← Build + push + deploy to staging
  make rollback       ← Rollback last production deploy

CODESPACES / DEV CONTAINERS:
  .devcontainer/devcontainer.json ← Pre-configured with all required tools
  → Python / Node.js + test frameworks + OTel + Kafka CLI + kubectl

DOCUMENTATION:
  make docs-serve     ← MkDocs local preview (docs + API specs)
  make openapi-ui     ← Swagger UI for REST APIs
  make asyncapi-ui    ← AsyncAPI Studio for event contracts
```

---

## Section 13 — FinOps & Cost Observability

```
METRICS (tracked in infrastructure/monitoring/grafana/dashboards/finops.json):
  ├── llm_token_usage_total      → Cost per feature / per agent / per request type
  ├── infra_cost_per_slo_met     → Infrastructure cost per SLO target achieved
  ├── cache_hit_rate             → LLM cache efficiency (reduces token cost)
  └── agent_action_cost_usd      → Estimated $ cost per autonomous action

GOVERNANCE:
  ├── Token budget per agent defined in config.py
  ├── Alert when monthly token spend > threshold
  └── Cost attribution tag: every LLM call includes service + feature tags
```

---

## Checklist — Gap Analysis for Existing Projects

Use this checklist to assess how an existing repository maps to this template:

```markdown
## Governance

- [ ] CLAUDE.md exists and is the behavioral contract for AI tooling
- [ ] All significant decisions have ADRs in docs/adr/
- [ ] Specs exist for all features before implementation (SDD)
- [ ] CONTRIBUTING.md and CODE_OF_CONDUCT.md are present

## Documentation

- [ ] README.md follows the minimum structure (Quick Start → API → Observability → On-call)
- [ ] CHANGELOG.md maintained with every release
- [ ] dependency-manifest.yaml with all deps, including AI dependencies
- [ ] SBOM generated and signed in CI

## Change Management

- [ ] RFC template exists and is used for Normal / Emergency changes
- [ ] CAB process documented
- [ ] deploy.sh, rollback.sh, smoke-test.sh are present and tested

## DevSecOps / Compliance

- [ ] SAST (Semgrep / CodeQL) configured and blocking
- [ ] DAST (OWASP ZAP) runs in staging pipeline
- [ ] Secret scanning configured (Gitleaks / TruffleHog)
- [ ] Container scanning (Trivy) in CI
- [ ] OWASP LLM Top 10 assessment documented

## AI Governance

- [ ] HITL gateway implemented for all production agent actions
- [ ] HOTL monitoring active for autonomous agent flows
- [ ] Prompt injection guard implemented (LLM01)
- [ ] PII filter implemented (LLM06)
- [ ] Action limits implemented (LLM08)
- [ ] Audit logger implemented (LLM09)
- [ ] Model Card created for every model in production
- [ ] EU AI Act compliance checklist completed

## Data Privacy

- [ ] PII inventory documented (docs/privacy/pii-inventory.md)
- [ ] PII masking applied before LLM ingestion, logging, and event publishing
- [ ] DPIA completed (GDPR) and RIPD completed (LGPD) before production
- [ ] Data retention policy implemented and automated
- [ ] Data subject rights mechanisms (access, deletion, portability) tested
- [ ] DPA references documented for all third-party processors

## SRE

- [ ] slo.yaml committed with all services
- [ ] Golden Signals dashboards created and linked from README
- [ ] PRR checklist completed before every production deploy
- [ ] CUJ files exist for all critical user journeys
- [ ] Runbooks reviewed by someone outside the authoring team
- [ ] Error budget policy documented

## Testing

- [ ] Unit test coverage ≥ 80%
- [ ] Integration tests cover key service boundaries
- [ ] Contract tests (Pact / OpenAPI) prevent breaking changes
- [ ] Performance tests establish baseline (k6 / Locust)
- [ ] Security tests cover OWASP Top 10 (Web + LLM)
- [ ] Chaos experiments run weekly in staging

## Async APIs

- [ ] AsyncAPI spec exists for all event-driven interfaces
- [ ] Dead Letter Queue configured for all consumers
- [ ] Schema registry in use (Avro / JSON Schema)
- [ ] PII masked before any event is published to broker
- [ ] Trace propagation enabled (W3C TraceContext in message headers)

## Scalability & Reliability

- [ ] HPA configured for all stateless services
- [ ] VPA configured (at least in recommendation mode)
- [ ] PodDisruptionBudget set (minimum 2 pods available)
- [ ] Multi-AZ anti-affinity rules applied
- [ ] Circuit breaker pattern implemented for external calls
- [ ] Feature flags in use for all new features and model rollouts
```

---

_Template version: 1.17.3 — Last updated: 2026-05-29_  
_Generic enterprise template — Agentic AI, DevSecOps, SRE, Privacy-first_
