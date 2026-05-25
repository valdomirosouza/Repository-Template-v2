# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Categories: `Added` | `Changed` | `Fixed` | `Security` | `Removed` | `Privacy` | `Deprecated`

Every entry must reference: Issue #, ADR # (if applicable), RFC # (if applicable).

---

## [Unreleased]

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

[Unreleased]: https://github.com/org/project/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/org/project/releases/tag/v0.1.0
