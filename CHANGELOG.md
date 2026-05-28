# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Categories: `Added` | `Changed` | `Fixed` | `Security` | `Removed` | `Privacy` | `Deprecated`

Every entry must reference: Issue #, ADR # (if applicable), RFC # (if applicable).

---

## [Unreleased]

### Added

- **Database encryption at rest** (`src/shared/db_encryption.py`): AES-256-GCM
  field-level encryption for L1/L2 PII columns; `enc:v1:<base64>` wire format with
  version prefix for zero-downtime key rotation; plaintext passthrough for rolling
  migration; production guard in `Settings.reject_placeholder_secrets` (ADR-0018,
  SPEC-db-encryption-at-rest)
- **`PostgresVectorStore` encryption integration**: optional `EncryptedField`
  dependency encrypts `content` on write and decrypts on read (`src/memory/vector_store.py`)
- **Alembic migration 0002** (`enable_pgcrypto_vector`): enables `pgcrypto` and
  `vector` PostgreSQL extensions
- **Alembic migration 0003** (`create_agent_memory_documents`): creates
  `agent_memory_documents` table with IVFFlat index for cosine similarity search
- **`DB_ENCRYPTION_KEY` config** (`src/shared/config.py`): new `db_encryption_key`
  and `db_encryption_enabled` settings; `.env.example` updated with generation instructions
- **`cryptography>=42.0.0`** added as explicit dependency (`pyproject.toml`)

### Fixed

- **SQL injection** in `PostgresVectorStore._SEARCH`: `source_filter` was interpolated
  directly into the SQL string; replaced with two separate parameterised queries
  (`_SEARCH_ALL`, `_SEARCH_FILTERED`) using asyncpg `$3` binding (ADR-0018 §SQL
  Injection Fix)

---

## [1.4.1] - 2026-05-28

### Added

- **Canonical Glossary** (`docs/glossary.md`): expanded from ~30 terms to 131 terms across
  10 thematic sections — AI Governance & Agents, Privacy & Data Protection, Compliance & Legal,
  Security, SRE & Reliability, Observability, Infrastructure & Middleware, APIs & Protocols,
  Development Practices & SDLC, Python & Framework Stack. Covers all abbreviations and
  domain terms used across specs, ADRs, skills, and source code.

---

## [1.4.0] - 2026-05-28

### Added

- **Architecture diagrams** (7 Mermaid diagrams): system topology + request lifecycle
  sequence (`docs/architecture.md`), request state machine, HITL/HOTL decision flowchart,
  4-layer guardrail pipeline, Kafka event topology, multi-agent harness sprint loop
- **RiskScorer** (`src/agents/risk_scorer.py`): deterministic 5-factor weighted risk scorer
  (irreversibility 0.35, external effect 0.25, scale 0.20, data sensitivity 0.15, rejection
  rate 0.05); replaces LLM self-reported `risk_score` in the orchestrator `_act` phase;
  47 unit tests with 100% branch coverage
- **Data retention job** (`src/jobs/retention_job.py`): `RetentionJob` enforces
  `specs/privacy/data-retention.md` — deletes expired `agent_memory_documents`, archives
  and hard-deletes aged `audit_events`, verifies compliance post-sweep
- **Retention CronJob** (`infrastructure/k8s/retention-cronjob.yaml`): daily 02:00 UTC
  K8s CronJob with dedicated `retention-job` ServiceAccount (DBA role for audit DELETE)
- **HITL notification spec** (`specs/ai/hitl-notification.md`): webhook payload schema,
  HMAC-SHA256 signature, 3-attempt retry policy, `NotificationService` protocol,
  `MultiChannelNotificationService` fan-out, reviewer dashboard contract, observability
- **CUSTOMISING.md**: full template adoption guide — minimum required changes, what to
  remove per stack, SDD first-spec walkthrough, harness_mode selection guide, upstream sync
- **Control loop specs**:
  - `specs/ai/feedback-loop.md`: convergence contract, thresholds table, worked 7-cycle
    example, rollback/override procedures, Mermaid control loop diagram
  - `specs/ai/agent-memory.md`: memory recall sequence diagram showing explicit recall
    in the Reason phase, injection API, and skip conditions

### Changed

- **README**: added 3-command end-to-end demo, `make infra-up` port/role table, health
  check verification step (`/health` + `/ready`), and "what to remove" per-stack guidance
- **`src/agents/orchestrator/orchestrator.py`**: `RiskScorer` injected as optional
  dependency; authoritative `risk_score` computed in `_act` before HITL routing

---

## [1.3.1] - 2026-05-27

### Changed

- **CLAUDE.md**: added Section 0 (development commands — setup, run, test, lint, docs) and
  Section 0.1 (architecture overview — request pipeline, key layers, infrastructure fallback
  pattern, harness modes, autonomy levels); updated file header to standard Claude Code prefix.

---

## [1.3.0] - 2026-05-27

### Added

- **A1 — AI Dependency Manifest**: `docs/dependency-manifest.yaml` — canonical AI dependency
  manifest complementing SBOM; documents Claude model IDs, API versions, onboarding dates,
  data classification, and governance controls (ADR-0010, ADR-0012); uploaded as artifact in `sbom.yml`

- **A2 — Sandbox Executor** (ADR-0016, SPEC-sandbox-execution):
  - `src/agents/sandbox_executor.py`: `SandboxExecutor` executes agent-generated commands inside
    ephemeral Docker containers with `--network none`, CPU/memory caps, zero host-env leakage,
    configurable timeout; controlled by `sandbox-mode` OpenFeature flag (3 variants)
  - `specs/ai/sandbox-execution.md`, `docs/adr/ADR-0016-agent-sandbox-execution-policy.md`
  - `infrastructure/feature-flags/flags/sandbox-mode.yaml`, `docker-compose.sandbox.yml`
  - 28 unit tests (98% coverage)

- **A3 — Feedback Loop** (SPEC-feedback-loop):
  - `src/agents/feedback_loop.py`: `FeedbackLoop` queries Prometheus for HITL rejection/approval
    rates per `action_type` and adjusts `risk_score` bias; publishes to Kafka `agent.feedback.applied`
  - `src/observability/metrics.py`: 3 new feedback metrics (Gauge × 2, Counter × 1)
  - `infrastructure/monitoring/grafana/dashboards/agent-feedback-loop.json`: 7-panel dashboard
  - `docs/api/asyncapi/v1/asyncapi.yaml`: `agent.feedback.applied` channel added
  - `Makefile`: `agent-feedback-check` target
  - 21 unit tests (92% coverage)

- **B1 — Granular Autonomy Levels** (`specs/ai/autonomous-mode-levels.md`, ADR-0015 rev):
  - `src/shared/feature_flags.py`: `get_autonomy_level(action_type, risk_score) → AutonomyLevel`
    with 5 graduated levels: FULL → MEDIUM_RISK → LOW_RISK → TESTS_ONLY → READ_ONLY → NONE
  - Five new flagd flag definitions in `infrastructure/feature-flags/flags/`
  - `tests/unit/shared/test_feature_flags.py`: 28 tests (was 6)

- **B2 — Agent Supervision Dashboard** (`specs/observability/agent-supervision.md`):
  - `infrastructure/monitoring/grafana/dashboards/agent-supervision.json`: 11-panel Grafana
    dashboard (Active HITL Queue, HITL by Agent, Approval/Rejection Rate, Wait Time p50/p99,
    Action Latency, LLM Token Budget, Autonomous Resolution Rate, Jaeger trace deep-link)

- **B4 — Self-Reflection & Auto-Correction** (`specs/ai/harness-design.md §9`):
  - `src/agents/harness/decision_tree_logger.py`: `DecisionTreeLogger` records every
    branching decision to the immutable audit log (`action = "decision_bifurcation"`)
  - `src/agents/harness/models.py`: added `DecisionPoint`, `PatchProposal`, `ExecutionSummary`
  - `src/agents/harness/coordinator.py`: PatchProposal via LLM self-reflection after
    `harness_patch_proposal_threshold` failures; ExecutionSummary attached to HITL payloads
  - 28 unit tests

- **B3 — Persistent Agent Memory** (`specs/ai/agent-memory.md`, ADR-0017):
  - `src/memory/vector_store.py`: `VectorStore` protocol + `InMemoryVectorStore` + `PostgresVectorStore`
  - `src/memory/document_indexer.py`: indexes `specs/` and `docs/adr/` via `pii_filter`
  - `src/memory/session_memory.py`: Redis-backed session cache, 24 h TTL default
  - `src/memory/bug_history_store.py`: HITL rejection recall via semantic similarity
  - `docs/privacy/dpia/dpia-agent-memory.md`: DPIA draft (DPO sign-off pending)
  - `.github/workflows/index-docs.yml`: auto-indexes on push to main
  - 58 unit tests

- **D1 — Vibe-to-Agentic Onboarding Guide** (Issue #12):
  - `docs/quickstart/vibe-to-agentic.md`: 3-level progressive onboarding guide
    (Level 1 Vibe Mode — day one safe prompts; Level 2 Supervised Agentic — reading
    `EvaluatorScore` / `ExecutionSummary`, HITL checkpoints; Level 3 Full Agentic —
    configuring `AutonomyLevel` per action type, tuning `risk_score` thresholds,
    interpreting audit log failure patterns, monitoring SLOs)
  - Includes explicit developer-autonomy risk warning and SDD mandatory-cycle reminder

- **C1 — Agent MTTD/MTTR Metrics** (`specs/observability/agent-performance.md`):
  - `src/observability/metrics.py`: 4 new metrics — `agent_mttd_seconds` (Histogram),
    `agent_mttr_seconds` (Histogram), `agent_autonomous_resolution_rate` (Gauge),
    `agent_cost_per_resolution_tokens` (Histogram); `record_agent_performance()` helper
  - `infrastructure/monitoring/grafana/dashboards/agent-performance.json`: 4-panel dashboard
    (MTTD p50/p99, MTTR p50/p99, autonomous resolution rate gauge, cost per resolution p50/p99)
  - SLO targets: MTTD p99 ≤ 60 s, MTTR p99 ≤ 600 s, resolution rate ≥ 80%, cost p99 ≤ 10 000 tokens
  - 17 unit tests

- **C2 — Hybrid Workflow Docs**:
  - `docs/quickstart/hybrid-workflow.md`: 4-phase Vibe → Agêntico cycle guide
    (Explore, Supervised Agêntico, Full Agêntico, Review & Land) with phase entry/exit conditions
    and governance gates
  - `CLAUDE.md §9`: Hybrid Workflow Mode section with phase table and ADR-0015 governance gate

- **C3 — Agent Chaos Experiments**:
  - `tests/chaos/experiments/agent-context-overflow.yaml`: oversized context truncation + no 500s
  - `tests/chaos/experiments/hitl-store-degradation.yaml`: Redis latency + outage; no silent approval
  - `tests/chaos/experiments/prompt-injection-under-load.yaml`: 50 concurrent injections; all blocked 400
  - `tests/chaos/experiments/evaluator-disagreement.yaml`: split PASS/FAIL verdict triggers HITL
  - `tests/chaos/experiments/llm-api-timeout.yaml`: Toxiproxy timeout; back-off + HITL escalation

- **C4 — Inter-Agent Protocol** (`specs/ai/harness-design.md`):
  - `infrastructure/proto/harness_state.proto`: `HarnessStateEnvelope` with `correlation_id`,
    sprint status enum, `oneof` payload (SprintStarted, SprintEvaluated, PatchProposalApplied,
    SprintEscalated, SprintCompleted)
  - `docs/api/asyncapi/v1/asyncapi.yaml`: `agent.harness.state` channel +
    `HarnessStateChanged` message + `HarnessStateChangedPayload` schema
  - `src/agents/harness/models.py`: `correlation_id` added to `TaskBrief`, `SprintContract`,
    `HarnessResult`, `ExecutionSummary`
  - `src/agents/harness/coordinator.py`: propagates `correlation_id` through sprint lifecycle
    and audit log events

### Changed

- `CLAUDE.md` §3.3: added sandbox rule — "NEVER execute agent-generated code outside
  `src/agents/sandbox_executor.py` without explicit HITL approval" (ADR-0016)
- `CLAUDE.md` §9: added Hybrid Workflow Mode section (C2)
- `src/shared/config.py`: added `sandbox_*`, `feedback_*`, `memory_*`, and
  `harness_patch_proposal_threshold` settings

### Fixed

- `src/shared/llm_client.py`: added `AnthropicLLMClient` — was imported by
  `src/workers/request_consumer.py` at module level but never defined, causing
  `ImportError` on worker startup (latent production bug)
- `tests/unit/agents/test_request_consumer.py`: `RequestConsumer` now has 100%
  unit test coverage (was 0%)

### Privacy

- `docs/privacy/dpia/dpia-agent-memory.md`: DPIA v1.1 — DPO sign-off complete
  2026-05-27; all five §4 items approved; Agent Memory feature cleared for
  production traffic (ADR-0017)

---

## [1.2.1] - 2026-05-26

### Added

- `docs/audit/expert-audit-2026-05-26.md`: audit summary document — 18 findings across four
  severity tiers, per-commit breakdown, and test impact table (PR #7)

---

## [1.2.0] - 2026-05-26

### Fixed

- `src/api/rest/routers/hitl.py`: `hitl_status` endpoint replaced stale `gateway._requests`
  dict access (AttributeError 500) with `gateway._store.pending_count()` — aligned with the
  HITLStore protocol introduced in Wave 3b (ADR-0011)
- `src/observability/metrics.py`: removed duplicate `ACTIVE_HITL_REQUESTS.dec()` from
  `record_hitl_decision()` — gauge lifecycle is the gateway's responsibility; double-decrement
  drove the gauge negative on every approved/rejected decision (ADR-0011)
- `src/agents/hitl_gateway.py`: `record_decision()` now archives APPROVED/REJECTED requests
  via `store.archive()` so `pending_count()` stays accurate and the hard cap is not inflated
  by decided entries (ADR-0011)
- `harness/doc-check.yml`: `spec-exists` and `adr-current` gates rewritten to use
  `PR_BODY_FILE` (mirrors spec-compliance fix); removed `.git/MERGE_MSG` primary source which
  is only populated during local merges and causes false-passes in PR CI (specs/ai/guardrails.md)
- `src/agents/harness/coordinator.py`: PII masking applied pre-LLM (`_generate()`) and
  pre-HITL (`_escalate_to_hitl()`, `_review_spec_with_hitl()`) via `mask_text` / `mask_dict`
  — three mandatory interception points enforced (specs/ai/guardrails.md, ADR-0012)
- `src/agents/hitl_gateway.py`: `ACTIVE_HITL_REQUESTS` gauge now decrements correctly on
  APPROVED/REJECTED decisions — was only decrementing on EXPIRED (ADR-0011)
- `harness/code-check.yml`: `spec-compliance` gate rewritten to use `PR_BODY_FILE` and avoid
  false-pass when it is unset; set `blocking: false`
- `src/agents/harness/coordinator.py` (`_run_simplified`): uses caller-supplied
  `success_criteria` or a description-anchored fallback — removes vague generic criterion
  (specs/ai/harness-design.md §2)
- `skills/privacy/pii.md`: removed fictitious `L2_FIELD_NAMES` registry block; replaced with
  accurate guidance — masking is value-pattern-based, not field-name-based (ADR-0012)
- `src/agents/harness/models.py`: `TaskBrief` gains optional `success_criteria` field
- `harness/code-check.yml`: SAST gate replaced `semgrep || true` with `bandit -r src/ -ll`
  (authoritative SAST tool per `skills/devsecops/secret-scanning.md`)
- `harness/code-check.yml` / `harness/staging-check.yml`: pii-scan gate `|| true` bypass
  removed; staging-check regex fixed (`[^[]` instead of broken `[^\[MASKED]`)
- `skills/ai/guardrails.md` / `skills/privacy/pii.md`: `[TOKEN]` reclassified from L3 to L2
  (JWT/session tokens are Sensitive, not Internal) (ADR-0012)
- `src/guardrails/prompt_injection_guard.py`: dead `_check_length()` method removed (was
  defined but never called in `validate()`)

### Added

- `tests/unit/agents/test_hitl_gateway.py`: gauge-decrement tests (approved + rejected paths)
  and archive tests (approved, rejected, pending count accuracy)
- `tests/unit/guardrails/test_audit_logger.py`: 9 tests covering all 4 query filters, limit,
  copy-on-append, event ID return, and `AuditWriteError` propagation
- `tests/unit/guardrails/test_action_limits.py`: 8 tests for `check_scope_limit()` and the
  unified `check()` guardrail (scope denial, rate limit denial, within-limits pass)
- `tests/unit/api/test_hitl_router.py`: 4 tests covering HITL status endpoint (200 + 503)
  and decision endpoint (404 unknown + 200 valid approval)
- `tests/unit/agents/test_hitl_gateway.py`: `TestHITLGatewayInit` — verifies default
  `InMemoryHITLStore` is created when no store is supplied

---

## [1.1.1] - 2026-05-26

### Fixed

- `src/guardrails/pii_filter.py`: `_get_patterns()` promovido para `ClassVar` — 7 regexes compiladas uma vez no import em vez de a cada chamada a `detect()` / `mask_text()` (hot path: executa antes de todo log write e LLM call) (ADR-0012)
- `src/guardrails/prompt_injection_guard.py`: `RejectionReason.NESTED_INSTRUCTION` removido do enum — era dead code não utilizado pelo guard e exposto na API pública (ADR-0012)
- `src/shared/config.py`: `database_url` e `redis_url` agora validados em produção — placeholders rejeitados no startup (ADR-0008); `SECRET_KEY` com menos de 32 chars rejeitado quando `JWT_ALGORITHM=HS256`
- `src/shared/config.py`: `service_version` lido dinamicamente de `version.txt` em vez de hardcoded `"0.0.0"` (ADR-0002)
- `src/api/rest/main.py`: `AsyncGenerator[None, None]` corrigido para `AsyncGenerator[None]` — default arg desnecessário removido (UP043, Python 3.13)
- `alembic/versions/0001_create_audit_events.py`: role do DB lido do `alembic.ini` via `context.config.get_main_option("db_app_role", "app_user")` em vez de hardcoded; `REVOKE` envolto em guard `DO $$ IF EXISTS` para não falhar silenciosamente se a role não existir (ADR-0011)
- `alembic/env.py`: substituído `engine_from_config` síncrono por `create_async_engine` + `asyncio.run()` — codebase só tem asyncpg, sem psycopg2 (ADR-0002)
- `.github/workflows/ci.yml`: job `build` agora requer `[test-unit, test-security, test-integration]` — antes podia rodar com testes falhando; Kafka atualizado de `7.6.0` para `7.7.0`
- `.github/workflows/cd-production.yml`: gates de canary substituídos de `bc` (não disponível no ubuntu-latest) para `python3`; estratégias de deploy restritas a `[canary]`
- `docker-compose.yml`: Redis com `--save 60 1` (persistência activada); Kafka com listener `INTERNAL://kafka:29092` para comunicação inter-container sem usar o listener externo

### Added

- `tests/conftest.py`: fixtures `stub_llm` (`StubLLMClient`) e `audit_logger` (`AuditLogger` + `InMemoryAuditStorage`) disponíveis globalmente para todos os testes — elimina duplicação inline
- `mkdocs.yml`: configuração mínima do mkdocs-material criada — `make docs-serve` e `mkdocs build --strict` agora funcionam; nav cobre todos os docs existentes (ADRs, AI Governance, Privacy, SRE, Change Management)
- `.github/dependabot.yml`: Dependabot configurado para pip e github-actions com cadência semanal e limite de 5 PRs por ecossistema
- `infrastructure/message-broker/schema-registry/avro/`: 6 schemas Avro stub criados com os nomes exatos referenciados em `services.yaml` (`request-created-v1.avsc`, `hitl-decision-v1.avsc`, `audit-event-v1.avsc`, `domain-entity-created-v1.avsc`, `domain-entity-updated-v1.avsc`, `event-processed-v1.avsc`) — CI `contract-drift` agora passa (ADR-0003)
- `tests/unit/shared/test_config.py`: 3 novos testes — `DATABASE_URL` com placeholder rejeitado em produção, `REDIS_URL` com placeholder rejeitado em produção, `SECRET_KEY` curto com HS256 rejeitado

### Changed

- `pyproject.toml`: alinhado para Python 3.13 — `requires-python = ">=3.13"`, `ruff target-version = "py313"`, `mypy python_version = "3.13"`; adicionado `"alembic/**" = ["S608"]` em `per-file-ignores` (SQL dinâmico é padrão em migrations)
- `Dockerfile`: ambos os stages atualizados de `python:3.12-slim` para `python:3.13-slim`
- `.github/workflows/ci.yml`: todos os 4 steps `setup-python` atualizados de `"3.12"` para `"3.13"`
- `.env.example`: `REDIS_PASSWORD=devpassword` e `REDIS_URL` com senha adicionados; alinhado com `docker-compose.yml`
- `Makefile`: `make new-service` agora cria estrutura mínima Python (`src/<name>/`, `__init__.py`, `README.md`, `pyproject.toml`) em vez de diretório vazio
- `.gitignore`: `resumo-*.md` e `site/` adicionados para evitar commit de artifacts de sessão e build do mkdocs

### Removed

- `resumo-memória-2026-05-26.md`: artifact de sessão Claude Code removido do repositório

---

## [1.1.0] - 2026-05-26

### Added (multi-language template — Block 4)

- `.github/workflows/ci-java.yml`: Java CI pipeline — `lint-java` (Checkstyle + SpotBugs + OWASP dependency-check), `test-java-unit` (JaCoCo ≥ 80%), `test-java-integration` (PostgreSQL + Redis + Kafka services), `build-java` (Spring Boot buildpack); auto-discovers all `services/*/pom.xml`; triggered only on Java/contract file changes
- `.github/workflows/ci-go.yml`: Go CI pipeline — `lint-go` (golangci-lint + proto drift check), `test-go-unit` (race detector + 80% coverage gate), `test-go-integration` (PostgreSQL + Redis + Kafka services), `build-go`; auto-discovers all `services/*/go.mod`; triggered only on Go/proto file changes
- `.github/workflows/ci-frontend.yml`: Frontend CI pipeline — `lint-frontend` (ESLint + TypeScript + API client drift check), `test-frontend-unit` (Jest + 80% coverage gate), `test-frontend-e2e` (Playwright), `build-frontend` (Docker image); matrix over `app:` list; triggered only on `frontend/**` or OpenAPI changes
- `docs/quickstart/add-new-service.md`: step-by-step 10-step checklist for registering a new service — language selection table (Python/Java/Go criteria), directory scaffold, services.yaml registration, CODEOWNERS, Prometheus scrape config, K8s manifests, env vars, CI wiring, Dockerfile templates per language, spec-first requirement, day-1 PR checklist
- `infrastructure/k8s/service.yaml`: K8s ClusterIP Service manifest template for agent-service

### Changed (multi-language template — Block 4)

- `.github/workflows/ci.yml`: added `contract-drift` job — validates OpenAPI + AsyncAPI specs are parseable, proto files compile, and `services.yaml` schema file references all exist on disk
- `CONTRIBUTING.md`: added per-language test/lint command table to "Before opening a PR" section; added checklist items for `services.yaml` and Prometheus config when adding new services; linked to `add-new-service.md`
- `docs/quickstart/README.md`: added `add-new-service.md` row to "After reading your language guide" table; updated label to "read these in order"
- `Makefile`: added `new-service` scaffold target (`make new-service NAME=foo LANG=python|java|go`); creates directory structure, go.mod, K8s manifests from templates; updated `.PHONY` list

### Added (multi-language template — Block 3)

- `infrastructure/monitoring/prometheus/prometheus.yml`: Prometheus scrape config — jobs for api-gateway (port 8000 `/metrics`), domain-service (port 8080 `/actuator/prometheus`), event-worker (port 8090 `/metrics`), otel-collector self-telemetry; rule_files wired to golden-signals.yaml; commented stubs for postgres/kafka exporters
- `infrastructure/monitoring/grafana/provisioning/datasources/datasource.yml`: Grafana datasource provisioning — Prometheus as default datasource with exemplar→Jaeger trace linking; Jaeger datasource
- `infrastructure/monitoring/grafana/provisioning/dashboards/dashboard.yml`: Grafana dashboard provisioning — auto-loads all JSON dashboards from `/var/lib/grafana/dashboards` with 30s hot-reload
- `docker-compose.yml`: fixed Grafana volume mounts — provisioning directory now correctly wired (`./grafana/provisioning:/etc/grafana/provisioning`) and dashboard JSONs mounted at `/var/lib/grafana/dashboards`
- `docs/api/grpc/proto/ai_service.proto`: example proto file — `AgentService` (SubmitTask unary + WatchTask server-streaming) and `HITLService` (SubmitForApproval + GetDecision); replaces .gitkeep; includes field numbering rules and generation instructions
- `docs/quickstart/contract-driven-dev.md`: contract-driven development guide — OpenAPI→TypeScript/Java/Go/Python generation commands; AsyncAPI+Avro consumer patterns per language; gRPC stub generation per language; contract change workflow; CI diff-check pattern; quick-reference table of all generators
- `docs/quickstart/README.md`: added "After reading your language guide" row linking to contract-driven-dev.md

### Changed (multi-language template — Block 3)

- `Makefile`: added `gen-proto-python`, `gen-sources-java`, `gen-api-client-python` targets; updated `.PHONY` list

### Added (multi-language template — Block 2)

- `docker-compose.yml`: shared development infrastructure stack — PostgreSQL 16, Redis 7, Kafka 7.7 (KRaft), Schema Registry, OTel Collector, Jaeger, Prometheus, Grafana, flagd; healthchecks on all services; named volumes; monorepo-dev network
- `docker-compose.test.yml`: lightweight integration-test stack with offset ports (PG 5433, Redis 6380, Kafka 9093) and tmpfs for speed; no observability services
- `.env.example`: fully rewritten — organized into per-language sections (Python, Java, Go, Frontend, Jobs); REQUIRED vs OPTIONAL markers on every var; Spring Boot property name translations; test environment vars (TEST_DATABASE_URL etc.); security generation instructions
- `frontend/.env.example`: frontend-only env stub — NEXT*PUBLIC*\* vars only, browser-safe HTTP OTel endpoint, flagd OFREP URL; no secrets

### Changed (multi-language template — Block 2)

- `Makefile`: added `infra-up`, `infra-down`, `infra-reset`, `test-infra-up`, `test-infra-down` targets for managing docker-compose stacks; updated .PHONY list

### Added (multi-language template — Block 1)

- `docs/quickstart/java-backend.md`: Java/Spring Boot developer quickstart — prerequisites, project layout, setup steps, resilience patterns (Resilience4j), PII masking, HITL REST client, Kafka consumer, structured logging, Testcontainers conventions, key ADRs
- `docs/quickstart/go-backend.md`: Go developer quickstart — prerequisites, project layout, setup steps, circuit breaker (gobreaker), context timeouts, PII masking, HITL REST client, structured slog, OTel Go SDK, testcontainers-go conventions, key ADRs
- `docs/quickstart/frontend.md`: React/Next.js developer quickstart — prerequisites, project layout, generated API client (openapi-generator), React Query + HITL polling, PII masking in UI, OTel browser tracing, Jest + Playwright testing conventions, key ADRs
- `docs/quickstart/jobs-worker.md`: Scheduled jobs & batch worker quickstart — BaseJob interface, APScheduler registration, idempotency + checkpointing pattern, HITL routing from batch context, job README requirements, K8s CronJob deployment
- `services.yaml`: service catalog (root) — all services with language, type, port, image, owner, Kafka publish/subscribe topics, runtime dependencies, governing ADRs; topic catalogue with schema paths, partitions, retention
- `.devcontainer/devcontainer.json`: multi-language devcontainer — Python 3.12, Java 21, Go 1.23, Node 20, Docker-in-Docker, kubectl + helm; VS Code extensions for all languages; port forwarding for all services and infra
- `.devcontainer/post-create.sh`: automated post-create script — installs uv, pnpm, Go tools (air, golangci-lint, protoc plugins), Java/Maven verification, pre-commit hooks, copies .env.example, starts infra stack, runs Alembic migrations

### Changed (multi-language template — Block 1)

- `Makefile`: extended with per-language targets (`test-python`, `test-java`, `test-go`, `test-frontend`, `lint-*`, `format-*`, `build-*`, `run-*`); added `gen-proto-go`, `gen-api-client-ts`, `new-service` scaffold; legacy aliases preserved; `help` column width updated; `SERVICE` and `APP` variables added

### Added (documentation — post v1.0.0 audit)

- `infrastructure/README.md`: criado — overview de K8s manifests, probe configuration, HPA custom metrics, related ADRs
- `infrastructure/feature-flags/README.md`: criado — arquitetura OpenFeature + flagd, catálogo de flags, instruções para adicionar nova flag
- `SETUP/013-prompt.md`: criado — prompt de scaffolding para a camada de resiliência e maturidade de plataforma (retry, HITL store, feature flags, K8s, alembic, chaos experiments)

### Changed (documentation — post v1.0.0 audit)

- `README.md`: versão atualizada para 1.0.0; ADR-0014 e ADR-0015 adicionados à seção de ADRs chave; seção Feature Flags criada; CUJ-001 dashboard adicionado à tabela de Observability; RB-003-hitl-recovery adicionado à seção On-call; estrutura de repositório atualizada com novos módulos; seção "Harness Engineering & Design Audit" adicionada com scorecard D1–D8
- `CLAUDE.md`: `src/agents/hitl_store.py` e `src/shared/feature_flags.py` adicionados à tabela de File Ownership; `infrastructure/feature-flags/` adicionado à governança; rule 3.3 atualizada com referência ao controle HOTL via feature flag (ADR-0015)
- `docs/adr/README.md`: ADR-0015 (Feature Flag Strategy) adicionado ao Master Index
- `MONOREPO-STRUCTURE-EN.md`: `src/agents/` atualizado com `hitl_store.py` e subdiretório `harness/`; `src/shared/` atualizado com `retry.py`, `db_client.py`, `llm_client.py`, `feature_flags.py`
- `SETUP/README.md`: prompts 011 (Validation) e 012 (Postmortem) com descrições corrigidas (estavam trocadas); prompt 013 adicionado; file map atualizado com todos os arquivos das waves P1/P2/P3; versão do template bumped para 2.2.0

---

## [1.0.0] - 2026-05-25

### Added (P3 Wave 3c — platform maturity)

- `src/shared/feature_flags.py`: `is_autonomous_mode_enabled()` — thin OpenFeature SDK
  wrapper that evaluates the `autonomous-mode` flag; falls back to
  `settings.autonomous_mode_enabled` when the SDK is unavailable (ADR-0015)
- `docs/adr/ADR-0015-feature-flag-strategy.md`: documents choice of OpenFeature + flagd —
  vendor-neutral CNCF standard; provider swap (LaunchDarkly, Unleash) requires no
  application code changes
- `infrastructure/feature-flags/flags/autonomous-mode.yaml`: flag definition with
  `defaultVariant: "off"` (HITL required by default)
- `infrastructure/feature-flags/flagd.yaml`: k8s Deployment + Service + ConfigMap for
  flagd (lightweight OpenFeature evaluation server reading flags from mounted YAML)
- `infrastructure/k8s/prometheus-adapter-config.yaml`: Prometheus Adapter ConfigMap with
  rules mapping `agent_semaphore_waiting` and `kafka_consumer_lag` to `custom.metrics.k8s.io`
- `tests/unit/shared/test_feature_flags.py`: 6 unit tests using `InMemoryProvider` —
  flag on/off, SDK-overrides-settings, fallback on SDK error

### Changed (P3 Wave 3c — platform maturity)

- `src/agents/orchestrator/orchestrator.py`: HITL routing now gated by
  `is_autonomous_mode_enabled()` — when autonomous mode is enabled (HOTL), high-risk
  actions bypass HITL approval; disabled by default for safety
- `infrastructure/k8s/hpa.yaml`: added custom-metric rules for `agent_semaphore_waiting`
  (scale when avg > 3 waiting per pod) and `kafka_consumer_lag` (scale when lag > 5000);
  added `behavior` block with stabilization windows to prevent thrashing (PRR-CAP-001)
- `pyproject.toml`: added `openfeature-sdk>=0.4.0` to runtime dependencies

### Added (P3 Wave 3b — HITL Redis persistence)

- `src/agents/hitl_store.py`: `HITLStore` Protocol + `InMemoryHITLStore` + `HITLRedisStore` —
  pluggable persistence backends for HITL requests; Redis-backed store survives pod restarts
  (ADR-0011). Schema: `hitl:req:{id}` (active, TTL = expires_at + 24 h grace),
  `hitl:pending` sorted set (score = expires_at timestamp), `hitl:expired:{id}` (7-day audit archive)
- `docs/runbooks/RB-003-hitl-recovery.md`: HITL recovery runbook covering pod restart, Redis
  failover, stuck queue, capacity exhaustion, and manual key inspection (satisfies PRR-OPS-002)
- `tests/integration/test_hitl_redis_store.py`: 14 integration tests for `HITLRedisStore`
  using `fakeredis` (no external service required) — save/get round-trip, TTL semantics,
  archive, pending-expired queries

### Changed (P3 Wave 3b — HITL Redis persistence)

- `src/agents/hitl_gateway.py`: `HITLGateway` now accepts an injectable `store: HITLStore`
  parameter; defines `HITLStore` Protocol; defaults to `InMemoryHITLStore` via lazy import
  when no store is provided — breaks no existing callers
- `src/api/rest/main.py`: lifespan startup selects `HITLRedisStore` when Redis is available,
  falls back to `InMemoryHITLStore` for local dev; wires store into `HITLGateway`
- `src/shared/config.py`: added `hitl_redis_key_prefix`, `hitl_redis_ttl_grace_hours`,
  `hitl_expired_ttl_days` configuration fields
- `tests/unit/agents/test_hitl_gateway.py`: updated to construct `InMemoryHITLStore` explicitly
  and inject into `HITLGateway`; assertions updated from direct dict access to store API
- `pyproject.toml`: added `fakeredis>=2.0.0` to dev dependencies

### Added (P3 Wave 3a — quick wins)

- `infrastructure/k8s/deployment.yaml`: `startupProbe` added (httpGet `/health`,
  `failureThreshold: 30`, `periodSeconds: 10` — 5-minute startup window). Prevents
  premature liveness kills during slow boot (asyncpg pool + Redis ping). Reduced
  `livenessProbe.initialDelaySeconds` from 15 → 5 since startupProbe owns the
  startup gate.
- `infrastructure/monitoring/grafana/cuj-dashboards/CUJ-001-user-request-processing.json`:
  Grafana dashboard covering all 7 steps of CUJ-001 with 12 panels — SLO stat rows
  (availability ≥ 99.9%, p99 latency ≤ 500ms, HITL approval ≤ 300s, error budget),
  time-series for request rate/latency/HITL queue/decisions/semaphore saturation/LLM
  tokens/DLQ depth. Satisfies PRR-OBS-005 (blocking).

### Added (harness audit P2 — operational resilience)

- `src/shared/db_client.py`: `ResilientDBPool` — wraps `asyncpg.Pool` with per-call
  `asyncio.wait_for` timeout, exponential-backoff retry via `with_retry`, and three-state
  circuit breaker via `CircuitBreaker`; reuses existing patterns from `retry.py` (ADR-0002)
- `src/api/rest/main.py`: `asyncio.Semaphore(settings.max_concurrent_agents)` created at
  startup — caps simultaneous agent coroutines to prevent event-loop starvation under burst load
- `src/observability/metrics.py`: `AGENT_SEMAPHORE_WAITING` gauge (requests waiting for a slot)
  and `DLQ_MESSAGES_COUNTER` counter (messages routed to Dead Letter Queue)
- `tests/unit/shared/test_db_client.py`: 9 unit tests — happy path, circuit breaker states,
  timeout propagation
- `tests/unit/agents/test_hitl_gateway.py`: 7 unit tests — hard cap enforcement, post-expiry
  eviction, slot recycling after eviction
- `tests/unit/api/test_requests_semaphore.py`: 4 unit tests — 503 + `Retry-After` when all
  slots occupied, 202 when capacity available, backwards-compatibility without semaphore state

### Fixed (harness audit P2 — operational resilience)

- `src/api/rest/main.py`: DB pool now wrapped in `ResilientDBPool` — every query gets
  timeout + retry + circuit breaker protection (previously unguarded)
- `src/guardrails/audit_logger.py`: `PostgresAuditStorage` type annotation updated to accept
  `ResilientDBPool` alongside `asyncpg.Pool` — no runtime behaviour change
- `src/agents/hitl_gateway.py`: `expire_stale_requests()` now evicts expired entries from
  `_requests` dict after marking them EXPIRED — prevents unbounded memory growth
- `src/agents/hitl_gateway.py`: `submit_for_approval()` raises `HITLGatewayError` when store
  reaches `settings.hitl_max_pending_requests` — explicit backpressure instead of silent OOM
- `src/shared/config.py`: added `max_concurrent_agents: int = 20` and
  `hitl_max_pending_requests: int = 500` configuration fields
- `src/api/rest/routers/requests.py`: endpoint returns 503 + `Retry-After: 5` header when
  `agent_semaphore._value == 0` — operationally visible backpressure
- `tests/chaos/experiments/network-partition.yaml`: DLQ assertion regex escaped and aligned
  to real metric name `dlq_messages_total`
- `.github/workflows/chaos-schedule.yml`: schedule updated to weekday nightly runs
  (`0 2 * * 1-5`) — chaos experiments now committed and active in CI

### Fixed (harness audit P1 — production safety)

- `infrastructure/k8s/pdb.yaml`: `minAvailable` corrected from 1 → 2 to satisfy PRR-CAP-003;
  prevents zero-replica windows during node drains with a 2-replica deployment
- `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`: `AgentActionErrorRate` query
  label corrected from `outcome=` to `result=` to match `agent_actions_total` label in `metrics.py`
- `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`: `LLMTokenBudgetNearing` query
  fixed to use actual metric names (`llm_tokens_total{token_type="input"}` / `llm_tokens_budget_total`)
- `src/api/rest/main.py`: `asyncpg.create_pool()` wrapped in `asyncio.wait_for(timeout=15s)` and
  Redis ping wrapped in `asyncio.wait_for(timeout=5s)` to prevent infinite boot loops on
  unresponsive dependencies
- `src/api/rest/main.py`: `InMemoryAuditStorage` fallback now raises `RuntimeError` when
  `app_env == "production"` — prevents silent audit record loss on pod restart

### Added (harness audit P1 — production safety)

- `src/shared/config.py`: `model_validator` rejects placeholder secrets (`LLM_API_KEY`,
  `SECRET_KEY`) when `app_env == "production"` — fail-fast at startup prevents misconfigured pods
  from reaching first LLM call
- `src/observability/metrics.py`: `LLM_TOKEN_BUDGET` gauge (`llm_tokens_budget_total`) and
  `init_budget_gauge()` helper — sets the static monthly budget at startup so the
  `LLMTokenBudgetNearing` alert can compute a ratio
- `tests/unit/shared/test_config.py`: 7 unit tests covering production secret validation
  (placeholder rejection, environment scoping, case-insensitivity)
- `tests/unit/shared/test_metrics.py`: 3 unit tests for `init_budget_gauge()` and
  `LLM_TOKEN_BUDGET` gauge behaviour

### Added (harness engineering compliance — ADR-0014, ADR-0011)

- `src/shared/retry.py` — `TransientError`, `CircuitBreakerError`, `with_retry()` tenacity decorator
  (exponential backoff + jitter), `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN state machine),
  `ResilientLLMClientWrapper` composing timeout + circuit breaker + retry (ADR-0014)
- `src/shared/llm_client.py`: `TimeoutLLMClientWrapper` applying `asyncio.wait_for` ceiling on
  all LLM calls — prevents event loop starvation from unresponsive upstream (ADR-0014)
- `src/guardrails/audit_logger.py`: `PostgresAuditStorage` full implementation backed by asyncpg;
  parameterized INSERT-only writes, parameterized SELECT with optional filters; wired as default
  production backend when DB pool is available (ADR-0011)
- `alembic/versions/0001_create_audit_events.py` — migration creating `audit_events` table with
  two composite indexes and `REVOKE UPDATE, DELETE` for append-only enforcement (ADR-0011)
- `alembic/env.py`, `alembic.ini` — Alembic configuration wired to `settings.database_url` (ADR-0002)
- `src/guardrails/action_limits.py`: `ActionLimiter.check(action_type, parameters)` — unified
  async entry point combining scope and rate checks; raises `ValueError` on denial (ADR-0014)
- `src/api/rest/_limiter.py` — shared slowapi `Limiter` singleton keyed by client IP (ADR-0002)
- `infrastructure/k8s/deployment.yaml` — K8s Deployment with liveness/readiness probes,
  `preStop` hook, resource requests/limits, and RollingUpdate strategy (ADR-0005)
- `infrastructure/k8s/service.yaml` — ClusterIP Service for agent-service (ADR-0005)
- `infrastructure/k8s/pdb.yaml` — PodDisruptionBudget `minAvailable: 1` (PRR-CAP-003) (ADR-0005)
- `infrastructure/k8s/hpa.yaml` — HorizontalPodAutoscaler 70% CPU target, 2–10 replicas
  (PRR-CAP-001) (ADR-0005)
- `tests/chaos/experiments/kill-agent.yaml` — Chaos Toolkit experiment: kill pod, verify
  Golden Signals recovery (specs/sre/game-day-playbook.md)
- `tests/chaos/experiments/network-partition.yaml` — Chaos Toolkit experiment: agent ↔ Kafka
  partition via Toxiproxy, verify DLQ routing and lag recovery (ADR-0007)
- `tests/chaos/experiments/broker-outage.yaml` — Chaos Toolkit experiment: Kafka StatefulSet
  scaled to 0, verify producer buffering and zero data loss (ADR-0007)
- `.github/workflows/chaos-schedule.yml` — weekly scheduled chaos CI running all three
  experiments against staging (specs/sre/game-day-playbook.md)

### Changed (harness engineering compliance — ADR-0014, ADR-0011)

- `src/api/rest/main.py`: lifespan now initializes asyncpg pool, Redis client, `AuditLogger`
  (PostgresAuditStorage in prod, InMemoryAuditStorage on failed pool), and `HITLGateway` in
  `app.state`; mounts `/metrics` ASGI app; registers slowapi middleware and rate-limit handler;
  wires OTel `FastAPIInstrumentor` (ADR-0002, ADR-0003, ADR-0011)
- `src/api/rest/routers/health.py`: `/ready` performs real asyncpg and Redis connectivity
  checks with `asyncio.wait_for` timeouts; returns 503 when either dependency is unreachable
  (ADR-0002)
- `src/api/rest/routers/hitl.py`: implemented `get_hitl_gateway` dependency, `hitl_status`
  returning real pending count from `app.state.hitl_gateway`, and `submit_decision` calling
  `gateway.record_decision()` (ADR-0011)
- `src/api/rest/routers/requests.py`: `submit_request` decorated with
  `@limiter.limit("{rate_limit_requests_per_minute}/minute")` to enforce per-IP rate limit
  (ADR-0002)
- `src/agents/hitl_gateway.py`: added `asyncio.Lock` protecting `_requests` dict; all
  read/write operations use phase-separated locking (state transition under lock, I/O outside)
  (ADR-0011)
- `src/agents/orchestrator/orchestrator.py`: `_act()` now `await`s `action_limiter.check()`
  using the new unified method signature (ADR-0014)
- `src/shared/config.py`: added `llm_call_timeout_seconds`, `redis_call_timeout_seconds`,
  `shutdown_drain_seconds`, `llm_circuit_breaker_threshold`, `llm_circuit_breaker_reset_seconds`,
  `llm_retry_max_attempts` (ADR-0014)
- `Dockerfile`: replaced `CMD` with `ENTRYPOINT` (exec form) and added `STOPSIGNAL SIGTERM`
  so uvicorn receives signals directly as PID 1 (ADR-0005)
- `pyproject.toml`: added `tenacity>=8.3.0` and `slowapi>=0.1.9` to production dependencies

### Added

- `.secrets.baseline` criado para habilitar `detect-secrets` no pre-commit hook (P2-01)
- Governance headers (`Owner`/`Reviewer`/`Status`/`Last updated`) adicionados aos 13 skill files (P2-03)

### Fixed

- `tests/unit/guardrails/test_pii_filter.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `tests/unit/guardrails/test_prompt_injection_guard.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `tests/security/test_pii_leakage.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `tests/security/test_owasp_llm_top10.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `specs/api/async-api-design.md`: Testing Requirements corrigido para documentar uso do
  `InMemoryProducer` para testes estruturais + Kafka real em CI (P2-05)

### Added

- Avro schemas (5 arquivos) em `infrastructure/message-broker/schema-registry/avro/` cobrindo
  todos os 8 event types do catálogo: `domain_request.avsc`, `agent_action.avsc`,
  `hitl_decision.avsc`, `domain_result.avsc`, `audit_event.avsc` (ADR-0003, ADR-0005)
- `tests/integration/test_kafka_events.py` — testes de contrato Kafka: envelope structure,
  PII masking pre-publish, topic naming convention, UUID v4 idempotency key,
  non-PII field preservation (ADR-0003, ADR-0012)

### Fixed

- `skills/ai/guardrails.md`: corrigidos nomes de métodos errados (`audit_logger.record()` →
  `await audit_logger.log_event(AuditEvent(...))`, `injection_guard.check()` →
  `injection_guard.validate()`, `result.rejected` → `not result.is_valid`,
  `result.category` → `result.rejection_reason`) (P0-01)
- `skills/ai/guardrails.md`: tokens de masking corrigidos de `[MASKED_L2]`/`[MASKED_L1]`
  para tokens por tipo `[EMAIL]`/`[CPF]` conforme implementação real em `pii_filter.py` (P0-02)
- `skills/privacy/pii.md`: tabela de Classification Levels e exemplo de teste corrigidos —
  `[MASKED_L1/L2/L3]` → `[CPF]`/`[CARD]`, `[EMAIL]`/`[PHONE]`/`[IP]`, `[TOKEN]`/`[UUID]`
  (P0-03, ADR-0012)
- `specs/ai/guardrails.md`: tabela de masking tokens no Layer 1 PII Filter corrigida para
  tokens por tipo, alinhando spec com código e ADR-0012 (P0-04 / P1-04)
- `src/shared/config.py`: adicionados `hitl_risk_threshold: float = 0.4` e
  `hotl_override_window_seconds: int = 300` — campos referenciados pelo orchestrator e
  ausentes da configuração (P0-05, ADR-0011, specs/ai/hitl-hotl.md)
- `specs/README.md`: `specs/api/async-api-design.md` registrado na tabela de ownership
  com Owner: Tech Lead, Reviewer: DevOps Lead, Status: Approved (P1-01)

### Added (harness design — ADR-0014)

- `docs/adr/ADR-0014-multi-agent-harness-strategy.md` — architectural decision capturing why
  multi-agent harness is needed (quality plateau, context exhaustion), Planner+Generator+Evaluator
  pattern, cost multipliers, and rejected alternatives (ADR-0014)
- `specs/ai/harness-design.md` — full harness design spec: agent roles, sprint contract schema,
  context management strategy, handoff model, harness modes, HITL integration, observability (ADR-0014)
- `src/agents/harness/models.py` — typed dataclasses: `TaskBrief`, `SprintContract`, `ProductSpec`,
  `GeneratorArtifact`, `EvaluatorScore`, `ContextSnapshot`, `HarnessResult` (ADR-0014)
- `src/agents/harness/context_manager.py` — `ContextManager` with `should_reset()`,
  `create_snapshot()` (decisions capped at 20/200 chars, PII safety-net applied),
  `restore_prompt()` (ADR-0014, specs/ai/harness-design.md §3)
- `src/agents/harness/planner.py` — `PlannerAgent` with injection guard, PII masking,
  LLM planning call, audit logging on `plan_generated` (ADR-0014, specs/ai/harness-design.md §1.1)
- `src/agents/harness/evaluator.py` — `EvaluatorAgent` with explicit skepticism system prompt,
  4-dimension scoring (quality/originality/craft/functionality), pass threshold per dimension
  (ADR-0014, specs/ai/harness-design.md §1.3)
- `src/agents/harness/coordinator.py` — `HarnessCoordinator` supporting solo/simplified/full modes;
  generate→evaluate→retry loop; HITL escalation on max iterations; optional spec HITL review
  (ADR-0014, specs/ai/harness-design.md §1.4)
- `src/shared/llm_client.py` — `LLMClient` Protocol + `StubLLMClient` for tests (ADR-0014)
- `skills/ai/harness.md` — multi-agent harness skill: mode selection table, sprint contract
  checklist, evaluator skepticism block, context reset pattern, HITL escalation protocol (ADR-0014)
- `tests/unit/agents/harness/test_context_manager.py` — 17 unit tests for `ContextManager`
  (should_reset, create_snapshot, restore_prompt) (ADR-0014)
- `tests/unit/agents/harness/test_evaluator.py` — 11 unit tests for `EvaluatorAgent`
  (pass/fail dimensions, threshold boundary, audit log, invalid JSON) (ADR-0014)
- `tests/unit/agents/harness/test_planner.py` — 10 unit tests for `PlannerAgent`
  (injection rejection, invalid JSON, audit log, missing contracts) (ADR-0014)
- `tests/unit/agents/test_orchestrator.py` — 9 unit tests for `AgentOrchestrator`
  (PII masking, injection guard, HITL routing, write-before-execute invariant) (ADR-0011, ADR-0014)
- `tests/integration/test_harness_pipeline.py` — 11 integration tests for end-to-end simplified
  harness pipeline (HarnessResult, artifact storage, evaluator audit log, no HITL escalation on
  first pass) (ADR-0014)

### Changed (harness design — ADR-0014)

- `src/shared/config.py`: added 7 harness settings fields (`harness_mode`, `harness_context_reset_threshold`,
  `harness_max_iterations`, `harness_evaluator_pass_threshold`, `harness_planner_enabled`,
  `harness_evaluator_enabled`, `harness_planner_hitl_review`) (ADR-0014)
- `src/agents/orchestrator/orchestrator.py`: closed `_reason()` and `_act()` `NotImplementedError`
  stubs; added LLM call with masked context, HITL routing via `HITLGateway`, write-before-execute
  audit log, `llm_client` constructor parameter (ADR-0010, ADR-0011)
- `CLAUDE.md`: added Multi-Agent Harness row to Skill Activation Table (ADR-0014)
- `skills/README.md`: added Multi-Agent Harness row to skill catalog (ADR-0014)
- `docs/adr/README.md`: added ADR-0014 row to Master Index (ADR-0014)
- `specs/README.md`: added `specs/ai/harness-design.md` to Ownership Table (ADR-0014)

### Added (anterior — P0/P1 audit sprint anterior)

- ADR-0002 through ADR-0009: Technology Stack, Async API, Observability, Message Broker,
  Deployment Strategy, Service Mesh, Secrets Management, Caching Strategy
- `pyproject.toml` with Ruff, mypy (strict), pytest, and Bandit configuration (R-01)
- `Dockerfile` multi-stage build (builder + production) with non-root user (R-02)
- `.pre-commit-config.yaml` enforcing Ruff, mypy, detect-secrets, and Bandit before commit (R-03)
- `version.txt` for Makefile version management (R-05)
- `specs/api/async-api-design.md` async API design rules and event catalogue (S-01)
- `docs/api/openapi/v1/openapi.yaml` REST API contract stub (T-04)
- `docs/api/asyncapi/v1/asyncapi.yaml` Kafka async event contract stub (T-04)
- `src/api/rest/main.py`, `routers/health.py`, `routers/requests.py`, `routers/hitl.py` — FastAPI stubs (T-02)
- `src/agents/orchestrator/orchestrator.py` — Perception→Reason→Act loop skeleton (T-05)
- `tests/integration/test_hitl_gateway_integration.py` — HITL lifecycle integration tests (T-01)
- `tests/integration/test_pii_filter_pipeline.py` — PII masking three-interception-point tests (T-01)
- `tests/integration/test_audit_logger_integration.py` — write-before-execute invariant tests (T-01)
- `skills/observability/otel-instrumentation.md` OTel spans, metrics, and logging skill (SK-02)
- `skills/api/rest-api-design.md` REST vs. async decision rules and security checklist (SK-01)
- `skills/devsecops/secret-scanning.md` SAST, detect-secrets, and dependency audit skill (SK-01)
- `skills/sdlc/spec-lifecycle.md` SDD spec writing and lifecycle skill (SK-01)

### Changed

- `CLAUDE.md`: added 4 new skills to the Skill Activation Table; fixed broken reference
  to `specs/api/async-api-design.md` (R-04)
- `skills/README.md`: catalog updated to include 4 new skills (SK-03)
- `src/*/`: all source modules now include `Spec:` and `ADR:` lines in module docstrings (T-03)
- `.github/workflows/ci.yml`: added `governance` job validating ADR index, skill paths,
  and spec paths on every PR (A-04, SK-03); fixed Kafka KRaft config removing
  Zookeeper dependency (R-06); added `detect-secrets` to lint job

---

## [0.1.0] - 2026-05-24

### Added

- Initial monorepo scaffold with full enterprise structure (Issue #1)
- `CLAUDE.md` behavioral contract for AI-assisted development
- Spec-Driven Development (SDD) workflow and 10-step standard process
- Architecture Decision Records framework (`docs/adr/`) with ADR-0001 through ADR-0013
- CI/CD pipeline with 5 stages: Validate → Test → Security → Build → Deploy (ADR-0006)
- Golden Signals observability stack: Prometheus + Grafana + OpenTelemetry (ADR-0004)
- HITL/HOTL human oversight model for AI agents (ADR-0011)
- PII masking guardrail with L1–L4 classification (`src/guardrails/pii_filter.py`) (ADR-0012)
- Prompt injection defense (`src/guardrails/prompt_injection_guard.py`) — OWASP LLM01
- Immutable audit logger for all agent actions (`src/guardrails/audit_logger.py`) — OWASP LLM09
- HITL gateway for human approval of agent actions (`src/agents/hitl_gateway.py`)
- Structured JSON logger with PII masking (`src/observability/logger.py`)
- OpenTelemetry bootstrap (`src/observability/otel_setup.py`)
- Prometheus Golden Signals metrics (`src/observability/metrics.py`)
- Pydantic Settings configuration (`src/shared/config.py`)
- SLO/SLI definitions template (`docs/sre/slo/slo.yaml`)
- Production Readiness Review template (`docs/sre/prr/PRR-TEMPLATE.md`)
- Critical User Journey template (`docs/sre/cuj/CUJ-001-user-request-processing.md`)
- Data privacy documentation: DPIA (GDPR Art. 35), RIPD (LGPD Art. 38), PII inventory
- EU AI Act compliance checklist (`docs/ai-governance/eu-ai-act-compliance.md`)
- NIST AI RMF mapping (`docs/ai-governance/nist-ai-rmf.md`)
- Change management process with RFC and CAB (`docs/change-management/`)
- Runbooks: rollback procedure, disaster recovery
- Enterprise skills catalog (`skills/`)
- Security tests for OWASP LLM Top 10 (`tests/security/test_owasp_llm_top10.py`)
- PII leakage test suite (`tests/security/test_pii_leakage.py`)
- Chaos engineering game day playbook (`tests/chaos/runbooks/game-day-playbook.md`)
- Canary + blue-green deploy scripts (`infrastructure/scripts/deploy/`)
- Async-first event topology with Kafka (ADR-0003, ADR-0005)

### Privacy

- PII inventory established with L1–L4 classification (Issue #1, ADR-0012)
- Data retention policy defined: 30d hot / 90d warm / 1y cold (ADR-0013)
- DPIA and RIPD templates created for GDPR Art. 35 and LGPD Art. 38 compliance
- Data Processing Register (RoPA) template created

[Unreleased]: https://github.com/valdomirosouza/template-monorepo/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/valdomirosouza/template-monorepo/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/valdomirosouza/template-monorepo/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/valdomirosouza/template-monorepo/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/valdomirosouza/template-monorepo/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/valdomirosouza/template-monorepo/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/valdomirosouza/template-monorepo/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/valdomirosouza/template-monorepo/releases/tag/v0.1.0
