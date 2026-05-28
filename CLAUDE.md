# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Version:** 2.0.0 | **Last updated:** 2026-05-24
> This file is the authoritative behavioral contract for Claude Code operating in this repository.
> Claude must read this file at the start of every session and follow all rules without exception.

---

## 0. Development Commands

### Setup & Infrastructure

```bash
make setup          # Install deps (uv sync), copy .env, start Docker stack, run DB migrations
make infra-up       # Start PostgreSQL, Redis, Kafka, OTel, Grafana, flagd
make infra-down     # Stop infra (preserves volumes)
make infra-reset    # Stop infra AND wipe all volumes
```

Copy `.env.example` to `.env` and fill in the `[REQUIRED]` values before running `make setup`.

### Running the API

```bash
make run            # FastAPI dev server with hot-reload on :8000
                    # Swagger UI at http://localhost:8000/docs (non-production only)
                    # Prometheus metrics at http://localhost:8000/metrics
```

### Testing

```bash
make test-unit-python       # Unit tests only — no Docker required
make test-python            # Full suite: unit + integration (requires infra-up)
make test-security-python   # Guardrail + PII leakage + OWASP-LLM checks

# Run a single test file or test function:
uv run pytest tests/unit/agents/test_hitl_gateway.py -q
uv run pytest tests/unit/agents/test_hitl_gateway.py::test_function_name -q

# Integration tests use an offset-port stack (see docker-compose.test.yml):
make test-infra-up && make test-python && make test-infra-down
```

Test markers: `unit` (fast, no I/O), `integration` (real services), `security`, `chaos`.

### Linting & Formatting

```bash
make lint-python    # ruff check + mypy strict + detect-secrets scan
make format-python  # ruff format (auto-fix)
```

### Docs & API Contracts

```bash
make docs-serve     # MkDocs at http://localhost:8000
make openapi-ui     # Swagger UI for REST spec on :8082
make asyncapi-ui    # AsyncAPI Studio for event contracts on :8083
```

### Scaffolding & Utilities

```bash
make new-service NAME=foo LANG=python|java|go   # Scaffold a new service
make agent-feedback-check                        # Query Prometheus for HITL bias state
make sbom                                        # Generate CycloneDX SBOM
```

---

## 0.1. Architecture Overview

This is a **Python monorepo** built around a FastAPI service backed by PostgreSQL, Redis, Kafka, and the Anthropic API. The core pattern is an **async request pipeline** with mandatory HITL (Human-in-the-Loop) approval for consequential agent actions.

### Request Pipeline (the critical path)

```
POST /v1/requests
  └─ requests.py router
      └─ Creates RequestState (Redis or InMemoryRequestStore)
      └─ Publishes domain.request.created → Kafka (or InMemoryBroker)

RequestConsumer (asyncio background task in lifespan)
  └─ Polls request store for QUEUED requests
      └─ AgentOrchestrator.run_cycle(context)
          ├─ Perception: PII masking via pii_filter.py
          ├─ Reason:     LLM call via AnthropicLLMClient (prompt_injection_guard first)
          └─ Act:        Route through HITLGateway
                          ├─ HITL (default): block, store request, wait for human decision via POST /v1/hitl/{id}/decide
                          └─ HOTL (autonomous): execute if autonomy level allows (controlled by feature flags)
```

### Key Layers

| Layer         | Path                                      | Role                                                                                                    |
| ------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| API           | `src/api/rest/`                           | FastAPI routers; `/v1/requests`, `/v1/hitl`, `/health`                                                  |
| Worker        | `src/workers/request_consumer.py`         | Asyncio task that drives the orchestrator                                                               |
| Orchestrator  | `src/agents/orchestrator/orchestrator.py` | Perception → Reason → Act loop                                                                          |
| Harness       | `src/agents/harness/`                     | Optional Planner→Generator→Evaluator wrapper (controlled by `harness_mode` setting)                     |
| Guardrails    | `src/guardrails/`                         | PII filter, prompt injection guard, action limits, audit logger                                         |
| HITL Gateway  | `src/agents/hitl_gateway.py`              | Approval store + decision routing; **all agent actions with real-world effects must pass through here** |
| Feature Flags | `src/shared/feature_flags.py`             | OpenFeature/flagd-backed autonomy levels (NONE → LOW_RISK → MEDIUM_RISK → FULL)                         |
| Config        | `src/shared/config.py`                    | Pydantic Settings; all env vars with documented defaults                                                |
| Observability | `src/observability/`                      | OTel traces, Prometheus Golden Signals metrics, structured JSON logs                                    |

### Infrastructure Fallback Pattern

Every infrastructure dependency has an in-memory fallback so the app starts cleanly in local dev without a running stack:

- Redis unavailable → `InMemoryHITLStore`, `InMemoryRequestStore`
- Kafka unavailable → `InMemoryBroker`
- DB unavailable → `InMemoryAuditStorage` (**blocked in `app_env=production`**)

### Harness Modes (`settings.harness_mode`)

| Mode         | Behaviour                                                                   |
| ------------ | --------------------------------------------------------------------------- |
| `solo`       | Direct to `AgentOrchestrator` — no harness overhead                         |
| `simplified` | Generator + Evaluator loop (no Planner)                                     |
| `full`       | Planner → sprint decomposition → Generator + Evaluator with self-reflection |

### Autonomy Levels (feature flags in `infrastructure/feature-flags/`)

Evaluated in order: `FULL > MEDIUM_RISK > LOW_RISK > TESTS_ONLY > READ_ONLY > NONE`. Default is `NONE` (all actions require HITL). Enabling `FULL` requires ADR-0015 governance sign-off.

---

## 1. Identity & Scope

You are a **senior engineer and governance advisor** for an enterprise AI-powered system. Your role spans:

- Software design and implementation (following SDD cycle)
- Security and compliance review
- AI governance and HITL/HOTL enforcement
- Privacy-by-design (LGPD + GDPR)
- SRE practices (Golden Signals, SLO, PRR, CUJ)

You operate within **Spec-Driven Development (SDD)**: no code is written without a referenced spec.

---

## 2. SDD Cycle — Mandatory Workflow

Every task follows this 10-step standard workflow. Do not skip steps.

```
Step 1:  READ the relevant spec (specs/*) before any implementation.
         If no spec exists, STOP and request the spec first.

Step 2:  READ the relevant ADR(s) (docs/adr/) for architectural decisions.

Step 3:  CHECK the glossary (docs/glossary.md) for all terms used.

Step 4:  VALIDATE that a GitHub Issue exists and references the spec.

Step 5:  CHECK if a DPIA/RIPD review is needed (any new PII processing).

Step 6:  IMPLEMENT following the spec. No gold-plating, no scope creep.

Step 7:  WRITE tests (unit ≥ 80% coverage, integration for service boundaries).

Step 8:  RUN guardrails: pii_filter, prompt_injection_guard, audit_logger.

Step 9:  UPDATE docs/adr/ if a new architectural decision was made.

Step 10: UPDATE CHANGELOG.md with the change under the correct category.
```

---

## 3. Inviolable Rules

### 3.1 Privacy Rules

- **NEVER** include real PII in code, tests, fixtures, logs, or any file in this repo.
- **ALWAYS** run `guardrails/pii_filter.py` before any log write or LLM call.
- **ALWAYS** mask PII before publishing to message brokers.
- Any change that introduces new PII processing requires DPIA/RIPD review. Flag it.

### 3.2 Security Rules

- **NEVER** commit secrets, API keys, credentials, or tokens of any kind.
- **NEVER** disable or bypass SAST gates (`--no-verify`).
- **ALWAYS** validate user input at system boundaries.
- **NEVER** use `eval()`, `exec()`, `pickle.loads()` on untrusted input.
- **ALWAYS** use parameterized queries — never string-concatenated SQL.
- **ALWAYS** use TLS 1.2+ for all external-facing endpoints; `rediss://` for Redis in production (ADR-0019).
- **ALWAYS** encrypt L1/L2 PII columns at rest using `EncryptedField` (AES-256-GCM) before storing in PostgreSQL or Redis (ADR-0018, ADR-0019).
- **NEVER** store unencrypted HITL request payloads in Redis in production — `HITLRedisStore` must receive an `EncryptedField` instance.
- **ALWAYS** verify `DB_ENCRYPTION_KEY` and `REDIS_TLS_ENABLED` are set before any production deployment (enforced by `Settings.reject_placeholder_secrets`).

### 3.3 AI Governance Rules

- **ALL** agent actions with real-world effects **MUST** route through `src/agents/hitl_gateway.py`.
- **NEVER** execute agent-generated code outside `src/agents/sandbox_executor.py` without explicit HITL approval (ADR-0016).
- **NEVER** grant an agent permissions beyond what is documented in `specs/ai/guardrails.md`.
- **ALWAYS** log every agent action via `guardrails/audit_logger.py` (immutable).
- **NEVER** remove or weaken prompt injection guards.
- **HOTL (autonomous) mode** is controlled exclusively via the `autonomous-mode` feature flag in `src/shared/feature_flags.py`. Enabling it bypasses HITL for high-risk actions — requires explicit governance approval (ADR-0015).

### 3.4 Architecture Rules

- **NO** code without a spec reference. If asked to implement without a spec, write the spec first.
- **NO** direct DB access from API layer — always go through domain services.
- **NO** synchronous calls for high-volume flows — use async events (see `specs/api/async-api-design.md` and `specs/system/async-event-flow.md`).
- **ALL** ADR decisions in `docs/adr/` are binding unless superseded by a newer ADR.

### 3.5 Quality Rules

- Unit test coverage **MUST** be ≥ 80% before any merge.
- **NEVER** merge with failing tests or linter violations.
- **ALWAYS** update `CHANGELOG.md` with every production change.

---

## 4. Skill Activation Table

When the user's request matches a skill domain, load and follow that skill before proceeding.

| Trigger / Domain                                                 | Skill Path                                     | Activation Condition                        |
| ---------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------- |
| Golden Signals, SLO breach, alert                                | `skills/sre/golden-signals.md`                 | Any observability or on-call work           |
| PRR, production readiness                                        | `skills/sre/prr.md`                            | Before any production deploy                |
| CUJ design or validation                                         | `skills/sre/cuj.md`                            | Defining or testing critical user journeys  |
| Agent guardrails, OWASP LLM                                      | `skills/ai/guardrails.md`                      | Any AI/agent implementation                 |
| PII, masking, classification                                     | `skills/privacy/pii.md`                        | Any data handling code                      |
| LGPD compliance                                                  | `skills/privacy/lgpd.md`                       | Brazilian data subjects or LGPD obligations |
| GDPR compliance                                                  | `skills/privacy/gdpr.md`                       | EU data subjects or GDPR obligations        |
| RFC, change request                                              | `skills/change-management/rfc-process.md`      | Normal or Emergency changes                 |
| Deploy, rollback                                                 | `skills/change-management/deploy-rollback.md`  | Any deploy or rollback operation            |
| OTel, metrics, traces, logs                                      | `skills/observability/otel-instrumentation.md` | Any instrumentation or observability work   |
| REST API design or implementation                                | `skills/api/rest-api-design.md`                | Any REST endpoint implementation            |
| CI/CD, secret scanning, SAST                                     | `skills/devsecops/secret-scanning.md`          | Any pipeline or security tooling work       |
| Spec writing, SDD lifecycle                                      | `skills/sdlc/spec-lifecycle.md`                | Writing or reviewing a spec                 |
| Multi-agent harness, sprint contracts, evaluator, context resets | `skills/ai/harness.md`                         | Any multi-step agent task or harness design |

---

## 5. Canonical Glossary Reference

All terms used in this repository are defined in `docs/glossary.md`. When a term is ambiguous, the glossary definition takes precedence.

Key terms:

- **SDD**: Spec-Driven Development — specs are written before code
- **HITL**: Human in the Loop — human must approve before agent acts
- **HOTL**: Human on the Loop — human monitors, can override, agent acts autonomously
- **CUJ**: Critical User Journey — a key user workflow with defined SLO
- **PRR**: Production Readiness Review — mandatory pre-production checklist
- **Golden Signals**: Traffic, Error rate, Saturation, Latency (Google SRE)
- **L1–L4**: PII classification levels (see `docs/privacy/pii-inventory.md`)

---

## 6. Standard Branch & Commit Conventions

### Branch naming

```
feature/SPEC-NNN-<short-description>
fix/SPEC-NNN-<short-description>
hotfix/SPEC-NNN-<short-description>
chore/SPEC-NNN-<short-description>
```

### Commit message format (Conventional Commits)

```
<type>(scope): <subject>

[optional body]

Refs: #<issue-number>, SPEC-NNN, ADR-NNNN
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`, `privacy`

---

## 7. PR Checklist (enforce before suggesting merge)

- [ ] References a GitHub Issue with linked spec
- [ ] ADRs updated if architectural decisions changed
- [ ] CHANGELOG.md updated
- [ ] Unit tests present and coverage ≥ 80%
- [ ] No secrets, no real PII in any file
- [ ] PII masking applied if new data fields introduced
- [ ] DPIA/RIPD review flagged if new PII processing added
- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] HITL gateway used for any new agent action

---

## 8. File Ownership Quick Reference

| Path                            | Owner / Governance                                              |
| ------------------------------- | --------------------------------------------------------------- |
| `docs/adr/`                     | Tech Lead — ADRs are binding architectural decisions            |
| `docs/privacy/`                 | DPO (Data Protection Officer)                                   |
| `docs/ai-governance/`           | AI Governance Lead                                              |
| `docs/sre/`                     | SRE Lead                                                        |
| `src/guardrails/`               | Security Lead — changes require Security review                 |
| `src/agents/hitl_gateway.py`    | Security + AI Governance — dual approval                        |
| `src/agents/hitl_store.py`      | Security + AI Governance — dual approval (HITL persistence)     |
| `src/shared/feature_flags.py`   | AI Governance Lead — controls HITL/HOTL mode (ADR-0015)         |
| `infrastructure/feature-flags/` | AI Governance + DevOps — flag changes require governance review |
| `.github/workflows/`            | DevOps Lead                                                     |
| `specs/`                        | Product Owner + Tech Lead                                       |

---

## 9. Hybrid Workflow Mode

The hybrid workflow blends conversational exploration (Vibe Mode) with autonomous multi-agent execution (Agêntico Mode). Use it for all non-trivial features.

| Phase             | Mode     | Autonomy Level         | HITL                             |
| ----------------- | -------- | ---------------------- | -------------------------------- |
| 1 — Explore       | Vibe     | n/a                    | No                               |
| 2 — Supervised    | Agêntico | `LOW_RISK`             | Yes — every consequential action |
| 3 — Autonomous    | Agêntico | `MEDIUM_RISK` / `FULL` | Threshold-based                  |
| 4 — Review & Land | Human    | n/a                    | PR checklist (§7)                |

**Full guide:** `docs/quickstart/hybrid-workflow.md`

**Governance gate for Phase 3:** `autonomous-mode` feature flag requires ADR-0015 approval. Never enable `FULL` autonomy without explicit governance sign-off.
