# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Categories: `Added` | `Changed` | `Fixed` | `Security` | `Removed` | `Privacy` | `Deprecated`

Every entry must reference: Issue #, ADR # (if applicable), RFC # (if applicable).

---

## [Unreleased]

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
