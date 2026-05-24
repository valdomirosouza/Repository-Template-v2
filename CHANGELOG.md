# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Categories: `Added` | `Changed` | `Fixed` | `Security` | `Removed` | `Privacy` | `Deprecated`

Every entry must reference: Issue #, ADR # (if applicable), RFC # (if applicable).

---

## [Unreleased]

### Added

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
