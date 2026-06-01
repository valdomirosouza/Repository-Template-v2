# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Version:** 1.26.19 | **Last updated:** 2026-06-01
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

Pre-commit hooks (`.pre-commit-config.yaml`) auto-run ruff, mypy, detect-secrets, and bandit on every `git commit`. Install once with `uv run pre-commit install`. The same gates run as blocking checks in `harness/code-check.yml` during CI.

### Docs & API Contracts

```bash
make docs-serve     # MkDocs at http://localhost:8000
make openapi-ui     # Swagger UI for REST spec on :8082
make asyncapi-ui    # AsyncAPI Studio for event contracts on :8083
```

### Other Languages (Java / Go / Frontend)

All targets accept a `SERVICE=<name>` or `APP=<name>` parameter matching the folder under `services/` or `frontend/`:

```bash
make test-unit-java SERVICE=domain-service   # Java unit tests (no Testcontainers)
make lint-java      SERVICE=domain-service   # Checkstyle + SpotBugs + OWASP dep-check
make run-java       SERVICE=domain-service   # Spring Boot dev server

make test-unit-go   SERVICE=event-worker     # Go unit tests (short mode)
make lint-go        SERVICE=event-worker     # golangci-lint
make run-go         SERVICE=event-worker     # air hot-reload

make test-unit-frontend APP=frontend         # Jest unit tests
make lint-frontend      APP=frontend         # ESLint + TypeScript type check
make run-frontend       APP=frontend         # Next.js dev server on :3000
```

### Database Migrations

```bash
uv run alembic upgrade head                          # Apply all pending migrations
uv run alembic revision --autogenerate -m "message"  # Generate a new migration
```

### Code Generation

```bash
make gen-proto-go                    # Regenerate Go gRPC stubs from proto files
make gen-proto-python                # Regenerate Python gRPC stubs
make gen-sources-java SERVICE=foo    # Run mvn generate-sources (OpenAPI stubs + Avro)
make gen-api-client-ts  APP=frontend # Regenerate TypeScript REST client from OpenAPI spec
make gen-api-client-python           # Regenerate Python REST client from OpenAPI spec
```

Event schemas (Avro) live in `infrastructure/message-broker/schema-registry/avro/`. Update them and re-run `gen-sources-java` when the event contract changes.

### Deploy & Rollback

```bash
make deploy-staging SERVICE=<name>   # Build, push, and helm-upgrade to staging
make rollback                        # Rollback the last staging deploy
```

### Scaffolding & Utilities

```bash
make new-service NAME=foo LANG=python|java|go   # Scaffold a new service
make agent-feedback-check                        # Query Prometheus for HITL bias state
make sbom                                        # Generate CycloneDX SBOM
make clean                                       # Remove build artefacts and caches
```

After scaffolding a new service, register it in `services.yaml` (the canonical service catalog) and add it to `.github/CODEOWNERS`.

---

## 0.1. Architecture Overview

This is a **multi-language monorepo template** (Python 3.13, Java/Spring Boot, Go, Node.js/Next.js) with a Python/FastAPI service as the active core. The example application ships an **async request pipeline** with an optional AI Agents extension (HITL/HOTL, guardrails, harness). AI/agent components are opt-in — projects that do not need them can delete `src/agents/`, `src/guardrails/`, and `src/memory/` entirely. See `CUSTOMISING.md` for what to remove or rename when adopting this as a project foundation.

`services.yaml` is the **canonical service registry** — every service with an API, Kafka topic, or K8s deployment must have an entry there. Topics defined in `services.yaml` must have a matching entry in `docs/api/asyncapi/v1/asyncapi.yaml`.

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
| Memory        | `src/memory/`                             | Session memory, vector store, document indexer, bug history (opt-in, ADR-0017)                          |
| Frontend      | `frontend/`                               | Next.js app; includes HITL operator approval UI                                                         |
| PR Gates      | `harness/`                                | Claude Code harness specs (code-check, doc-check, release-check, staging-check)                         |
| ADRs          | `docs/adr/`                               | ADR-0001–ADR-0029 all binding; 0026–0029 cover SOX audit log, ISO 27001 CM, DORA metrics, DevSecOps     |

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

You are a **senior engineer and governance advisor** for an enterprise software system. Your role spans:

- Software design and implementation (following SDD cycle)
- Security and compliance review
- Privacy-by-design (LGPD + GDPR)
- SRE practices (Golden Signals, SLO, PRR, CUJ)
- AI governance and HITL/HOTL enforcement _(only when the AI Agents extension is active)_

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
         See docs/privacy/ for DPIA/RIPD templates and the review process.

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
- OWASP Top 10 controls MUST be enforced at every API boundary:
  - A01 (Broken Access Control): RBAC enforced; no IDOR patterns; resource ownership validated.
  - A02 (Cryptographic Failures): TLS 1.2+ everywhere; AES-256-GCM at rest; no MD5/SHA-1.
  - A03 (Injection): parameterized queries only; prompt injection guard always on.
  - A04 (Insecure Design): threat model (`specs/security/threat-model.md`) updated each major release.
  - A05 (Security Misconfiguration): no default credentials; Trivy scan blocks on CRITICAL CVEs.
  - A06 (Vulnerable Components): SCA (OWASP dep-check / pip-audit) blocks on CRITICAL findings.
  - A07 (Auth Failures): JWT with short expiry; refresh token rotation; brute-force protection.
  - A08 (Software Integrity): Cosign-signed artifacts; SLSA Level 3 target; SBOM on every build.
  - A09 (Logging Failures): every 4xx/5xx logged with `request_id`; no PII in logs.
  - A10 (SSRF): outbound allow-list enforced; no user-controlled URLs in server-side fetches.
- OWASP LLM Top 10 controls MUST be enforced for every AI/agent path (when `src/agents/` is active):
  - LLM01 (Prompt Injection): `prompt_injection_guard.py` — never disabled.
  - LLM02 (Insecure Output Handling): all LLM output sanitized before rendering or executing.
  - LLM06 (Sensitive Info Disclosure): `pii_filter.py` runs before every LLM call and every log write.
  - LLM08 (Excessive Agency): HITL gateway enforced; autonomy level controlled by feature flags only.
  - LLM09 (Overreliance): evaluator in harness validates LLM output; human review threshold ≥ 0.7 risk score.
- DAST (OWASP ZAP full scan) MUST run in staging as a blocking gate before every production promotion.

### 3.3 AI Governance Rules

> **These rules apply ONLY when the AI Agents Module is enabled** (i.e., `src/agents/` is present).
> Projects that do not use AI agents can ignore this section entirely.
> See `docs/optional-extensions/ai-agents/README.md` for the activation checklist.

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

When the user's request matches a skill domain, **Read the skill file listed in the table and follow its guidance before writing any code**. These are plain Markdown files in the `skills/` directory — load them with the Read tool, not via the Claude Code Skill tool. The `.claude/skills/` directory is a parallel copy for the Claude Code Skill tool (used by `/`-commands) and does not replace this mechanism.

### Core Skills

| Trigger / Domain                                | Skill Path                                        | Activation Condition                                                   |
| ----------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------- |
| Golden Signals, SLO breach, alert               | `skills/sre/golden-signals.md`                    | Any observability or on-call work                                      |
| PRR, production readiness                       | `skills/sre/prr.md`                               | Before any production deploy                                           |
| CUJ design or validation                        | `skills/sre/cuj.md`                               | Defining or testing critical user journeys                             |
| Incident response, on-call, MTTD/MTTR           | `skills/sre/incident-response.md`                 | Production incident or escalation                                      |
| PII, masking, classification                    | `skills/privacy/pii.md`                           | Any data handling code                                                 |
| LGPD compliance                                 | `skills/privacy/lgpd.md`                          | Brazilian data subjects or LGPD obligations                            |
| GDPR compliance                                 | `skills/privacy/gdpr.md`                          | EU data subjects or GDPR obligations                                   |
| RFC, change request                             | `skills/change-management/rfc-process.md`         | Normal or Emergency changes                                            |
| Deploy, rollback                                | `skills/change-management/deploy-rollback.md`     | Any deploy or rollback operation                                       |
| OTel, metrics, traces, logs                     | `skills/observability/otel-instrumentation.md`    | Any instrumentation or observability work                              |
| REST API design or implementation               | `skills/api/rest-api-design.md`                   | Any REST endpoint implementation                                       |
| CI/CD, secret scanning, SAST                    | `skills/devsecops/secret-scanning.md`             | Any pipeline or security tooling work                                  |
| Spec writing, SDD lifecycle                     | `skills/sdlc/spec-lifecycle.md`                   | Writing or reviewing a spec                                            |
| Aggregates, entities, repositories, DDD         | `skills/domain/domain-modeling.md`                | Any domain model design, new entity, or service layer                  |
| Test pyramid, coverage, markers, contract tests | `skills/engineering/testing-strategy.md`          | Writing, reviewing, or debugging tests in any language                 |
| Ethical AI review, bias audit, EU AI Act        | `skills/ethics/ethical-ai-review.md`              | Any AI/agent feature, new action_type, or autonomy change              |
| SOX audit, financial data, access review        | `skills/compliance/sox.md`                        | **Only if organization is SEC-listed.** Any financial data path change |
| ISO 27001 change management, CAB, RFC           | `skills/compliance/iso27001-change-management.md` | Any production deploy or config change                                 |
| DORA metrics, deployment frequency, MTTR        | `skills/sre/dora-metrics.md`                      | Any pipeline or deploy work                                            |
| OWASP Top 10, DAST, vulnerability remediation   | `skills/devsecops/owasp-top10.md`                 | Any API endpoint, auth, or data handling change                        |
| DevSecOps pipeline, SAST, SCA, IaC scan         | `skills/devsecops/pipeline-security.md`           | Any CI/CD pipeline modification                                        |
| Token efficiency install, RTK setup             | `skills/token-efficiency/rtk-setup.md`            | First session on a new machine; "install rtk"                          |
| Test/lint/build/git/docker commands             | `skills/token-efficiency/rtk-commands.md`         | Any shell command execution                                            |
| Session start, context hygiene                  | `skills/token-efficiency/rtk-context-hygiene.md`  | Start of every Claude Code session                                     |

### AI Agents Module Skills _(opt-in — only when `src/agents/` is present)_

| Trigger / Domain                                                 | Skill Path                | Activation Condition                        |
| ---------------------------------------------------------------- | ------------------------- | ------------------------------------------- |
| Agent guardrails, OWASP LLM                                      | `skills/ai/guardrails.md` | Any AI/agent implementation                 |
| Multi-agent harness, sprint contracts, evaluator, context resets | `skills/ai/harness.md`    | Any multi-step agent task or harness design |

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

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`, `privacy`, `perf`, `ci`, `build`, `style`, `revert`

> The **squash-merge PR title** (not just commits) must match this Conventional-Commits grammar — it is validated by the `pr-governance` workflow and blocks merge if malformed.

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
- [ ] _(AI Agents Module only)_ HITL gateway used for any new agent action
- [ ] **[IF SOX APPLIES]** SOX: RFC_ID present in commit message for normal-change / emergency-change labels
- [ ] **[IF SOX APPLIES]** SOX: financial data write paths produce audit records (verify with `make test-security-python`)
- [ ] ISO 27001: change type label applied (`standard-change` / `normal-change` / `emergency-change`)
- [ ] ISO 27001: deploy-rollback skill followed; rollback tested in staging before production
- [ ] DORA: lead time from first commit to now is ≤ 24h target (or documented exception)
- [ ] OWASP: DAST (ZAP) scan passed in staging (link scan report in PR body)
- [ ] OWASP: no new CRITICAL/HIGH SAST or SCA findings without documented risk acceptance
- [ ] DevSecOps: container scan (Trivy) passed with zero CRITICAL CVEs
- [ ] DevSecOps: IaC scan (Checkov) passed on any `infrastructure/` changes
- [ ] DevSecOps: SBOM generated and signed (cosign attestation present)

### 7.1 CI-Enforced Gates (not just advisory)

The `pr-governance` workflow (`.github/workflows/pr-governance.yml`, REM-008/REM-010) turns several of the rules above into **blocking** PR checks. Know these before opening a PR:

- **Conventional PR title** — the squash-merge subject must match the grammar in §6.
- **CHANGELOG updated** — any non-docs change must touch `CHANGELOG.md` under `[Unreleased]`. Escape hatch: add the `skip-changelog` label. Docs-only PRs and Dependabot are auto-exempt.
- **Spec reference** — `feat`/`fix`/`security`/`privacy`/`perf` PRs must cite a spec (`SPEC-NNN`/`REM-NNN`) in title or body. Escape hatch: `no-spec` label.
- **Version consistency** — `version.txt` is the **single source of truth** for the project version (currently driven by REM-010). If you change `version.txt` or `pyproject.toml`, the two must agree, or the gate fails. Don't bump the version by hand in one place only.

The full pipeline (`ci.yml`) additionally runs jobs: `governance`, `lint`, `test-unit`, `test-integration`, `test-security`, `contract-drift`, `build`. The `harness/*.yml` specs (§0.1) are the Claude Code PR-review gates that complement these.

---

## 8. File Ownership Quick Reference

| Path                 | Owner / Governance                                   |
| -------------------- | ---------------------------------------------------- |
| `docs/adr/`          | Tech Lead — ADRs are binding architectural decisions |
| `docs/privacy/`      | DPO (Data Protection Officer)                        |
| `docs/sre/`          | SRE Lead                                             |
| `.github/workflows/` | DevOps Lead                                          |
| `specs/`             | Product Owner + Tech Lead                            |

**AI Agents Module paths** _(only relevant when the AI Agents extension is active)_

| Path                            | Owner / Governance                                              |
| ------------------------------- | --------------------------------------------------------------- |
| `docs/ai-governance/`           | AI Governance Lead                                              |
| `src/guardrails/`               | Security Lead — changes require Security review                 |
| `src/agents/hitl_gateway.py`    | Security + AI Governance — dual approval                        |
| `src/agents/hitl_store.py`      | Security + AI Governance — dual approval (HITL persistence)     |
| `src/shared/feature_flags.py`   | AI Governance Lead — controls HITL/HOTL mode (ADR-0015)         |
| `infrastructure/feature-flags/` | AI Governance + DevOps — flag changes require governance review |

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

---

## 10. SOX Compliance Rules

> **APPLICABILITY:** These rules are MANDATORY only for organizations subject to SEC reporting
> obligations (NYSE/NASDAQ-listed companies or SEC-regulated entities). For all other
> organizations these are RECOMMENDED best practices, not inviolable rules.
> If SOX does not apply to your organization, remove this section and the
> `skills/compliance/sox.md` activation row from the Skill Activation Table (§4).

- **[IF SOX APPLIES]** EVERY financial-data write path MUST produce an immutable audit record via `guardrails/audit_logger.py`.
- **[IF SOX APPLIES]** AUDIT log retention MUST be ≥ 7 years. Verify `docs/sox/` retention policy enforces this (ADR-0026).
- **[IF SOX APPLIES]** SEGREGATION OF DUTIES: the developer who writes code MUST NOT be the sole approver of their own PR for any change touching financial data paths. Enforce via CODEOWNERS (minimum 2 approvers on paths: `src/*`, `services/*`, `infrastructure/*`).
- **[IF SOX APPLIES]** CHANGE EVIDENCE: every production deployment MUST be traceable to an approved RFC with ticket ID in the merge commit. The `pr-governance` workflow must block merge without RFC_ID for `normal-change` and `emergency-change` labels.
- **[IF SOX APPLIES]** ACCESS REVIEW: privileged access to production secrets and DB encryption keys must be reviewed quarterly and documented in `docs/sox/access-review.md`.
- **[IF SOX APPLIES]** NEVER allow direct database writes from any service without a traceable `request_id` that appears in the audit log.

Full skill: `skills/compliance/sox.md` | Spec: `specs/compliance/sox-controls.md` | ADR: ADR-0026

---

## 11. ISO 27001 Change Management Rules

- ALL changes to production follow the three-tier change classification:
  - **Standard Change:** pre-approved, low-risk; deploy windows Mon–Thu 10:00–17:00.
  - **Normal Change:** RFC approved by CAB before merge; RFC_ID mandatory in merge commit (`Refs: RFC-NNNN`).
  - **Emergency Change:** TL + SecOps async approval; retroactive RFC within 24h; mandatory post-mortem.
- DEPLOY procedure: must follow `skills/change-management/deploy-rollback.md` — build → sign → SBOM → staging smoke → canary 5%→25%→100% with SLO gate.
- ROLLBACK procedure: `make rollback` must complete within the RTO defined in `docs/sre/slo/slo.yaml` (`dora_mttr_target_seconds: 3600`). Runbook RB-003 governs HITL recovery and rollback.
- EVERY deployment MUST record: deployer identity, RFC_ID, image digest (SHA-256), SBOM hash, and timestamp in `docs/change-log/` (append-only). Schema: `docs/change-log/SCHEMA.md`.
- CAB APPROVAL is required for Normal and Emergency changes before any production pipeline execution. The `cd-production.yml` workflow validates RFC approval status via the `cab-check` job before proceeding.
- CONFIGURATION items (infra, secrets, feature flags) are in scope for change management. Flag changes in `infrastructure/feature-flags/` require governance review per ADR-0015.

Full skill: `skills/compliance/iso27001-change-management.md` | Spec: `specs/compliance/iso27001-change-management.md` | ADR: ADR-0027

---

## 12. DORA Metrics — Mandatory Tracking

DORA Elite targets for this repository:

- **Deployment Frequency:** ≥ 1 deploy/day to staging; ≥ 1 deploy/week to production.
- **Lead Time for Changes:** p50 ≤ 24h from commit to production deploy.
- **Change Failure Rate:** < 5% of production deploys trigger rollback or hotfix.
- **Time to Restore Service:** MTTR p50 < 1h (enforced via `dora_mttr_target_seconds` in `docs/sre/slo/slo.yaml`).

Enforcement:

- Prometheus DORA dashboard MUST exist at `infrastructure/monitoring/grafana/dora-metrics.json`.
- `cd-production.yml` MUST emit a `dora_deployments_total` metric on every deploy (success/rollback/failure) via the `emit-dora-event` job.
- A monthly DORA report MUST be generated using the template in `specs/observability/dora-metrics.md §5` and stored as `docs/sre/dora-report-YYYY-MM.md`.
- LEAD TIME is measured from the first commit SHA on the PR to the production deploy timestamp.
- Any DORA metric falling below Elite → Medium threshold triggers a required retrospective within 5 business days.

Full skill: `skills/sre/dora-metrics.md` | Spec: `specs/observability/dora-metrics.md` | ADR: ADR-0028

---

## 13. Token Efficiency Rules

RTK (Rust Token Killer, https://github.com/rtk-ai/rtk) is installed and active in this repository.
The PreToolUse hook auto-rewrites bash commands. The rules below are in effect for
every Claude Code session. **Spec:** RTK-001 | **ADR:** ADR-0030

### 13.1 Mandatory: Always use RTK for high-output commands

NEVER run these commands without RTK prefix:

- `pytest` / any test runner → use `rtk pytest`, `rtk go test`, `rtk jest`
- `git status` / `git diff` / `git log` → use `rtk git <subcommand>`
- `docker ps` / `docker logs` / `kubectl logs` → use `rtk docker ...` / `rtk kubectl ...`
- `ls -la` on directories with >20 files → use `rtk ls`
- `ruff check` / `golangci-lint run` → use `rtk ruff check` / `rtk golangci-lint run`
- `cat` on files > 200 lines → use `rtk read <file>` or `head -N <file>`

The hook handles this automatically for bash tool calls. These rules apply when
explicitly constructing commands or in contexts where the hook may not apply.

### 13.2 Mandatory: Read files surgically

- NEVER read an entire file to locate a single function — use `grep -n` first
- NEVER load more than ONE skill file per task unless the task spans two explicit domains
- ALWAYS use `rtk ls` or `rtk smart <dir>` before reading individual files in an unfamiliar module

### 13.3 Mandatory: Prefer bash shell tools over built-in Read/Grep/Glob

Built-in tools bypass the PreToolUse hook. Prefer shell equivalents so RTK filtering applies:

- `cat file | head -N` over Read tool for large files
- `grep -rn "pattern" src/` over Grep tool for codebase search
- `find src/ -name "*.py"` over Glob tool for file discovery

Exception: for files < 100 lines, built-in Read tool is fine.

### 13.4 Skill activation

When the task involves token efficiency, install, or context hygiene:

| Trigger                                | Skill                                            |
| -------------------------------------- | ------------------------------------------------ |
| "install rtk", "set up token savings"  | `skills/token-efficiency/rtk-setup.md`           |
| Any test/lint/build/git/docker command | `skills/token-efficiency/rtk-commands.md`        |
| Session start, context window concerns | `skills/token-efficiency/rtk-context-hygiene.md` |

### 13.5 Weekly maintenance

Run `rtk discover --since 7` at the start of each week. Any command with 0% savings
that appears > 3 times should be added to `.rtk/filters.toml`.
