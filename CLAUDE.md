# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Version:** 2.8.0 | **Last updated:** 2026-06-14
> This file is the authoritative behavioral contract for Claude Code in this repository.
> Read it at the start of every session and follow all rules without exception. It overrides any default behavior.

---

## 0. Development Commands

Run `make help` for the full target list. All multi-language targets accept `SERVICE=<name>` (under `services/`) or `APP=<name>` (under `frontend/`). Copy `.env.example` to `.env` and fill `[REQUIRED]` values before `make setup`.

```bash
# Setup & infra — pick the smallest tier that fits (see SETUP.md), then `make smoke`
make setup-minimal    # Solo/PoC — deps + unit tests, no Docker
make setup-core       # PostgreSQL + Redis + observability
make setup-full       # Full enterprise stack (Kafka, Schema Registry, flagd, Alertmanager)
make setup            # uv sync, copy .env, start Docker stack, run migrations
make infra-up         # PostgreSQL, Redis, Kafka, OTel, Grafana, flagd
make infra-down       # Stop infra (preserves volumes)
make infra-reset      # Stop infra AND wipe volumes

# Run
make run              # FastAPI dev server :8000 (Swagger /docs non-prod, Prometheus /metrics)

# Test (Python)
make test-unit-python      # Unit only, no Docker
make test-python           # Unit + integration (needs infra-up)
make test-security-python  # Guardrail + PII leakage + OWASP-LLM
make test-infra-up && make test-python && make test-infra-down   # offset-port integration stack
uv run pytest tests/unit/agents/test_hitl_gateway.py -q          # single file
uv run pytest tests/unit/agents/test_hitl_gateway.py::test_x -q  # single function
uv run pytest tests/abuse_cases/ -m abuse_case                   # abuse-case suite (ADR-0050)
# Markers: unit, integration, security, chaos, abuse_case

# Lint & format (Python)
make lint-python      # ruff check + mypy strict + detect-secrets
make format-python    # ruff format

# Other languages (pass SERVICE=/APP=)
make test-unit-java SERVICE=domain-service   # also lint-java, run-java
make test-unit-go   SERVICE=event-worker     # also lint-go, run-go
make test-unit-frontend APP=frontend         # also lint-frontend, run-frontend (:3000)

# Docs & contracts
make docs-serve       # MkDocs :8000
make openapi-ui       # Swagger for REST spec :8082
make asyncapi-ui      # AsyncAPI Studio :8083

# DB migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "message"

# Codegen — gen-proto-go/-python, gen-sources-java SERVICE=foo, gen-api-client-ts APP=foo, gen-api-client-python
# Avro schemas live in infrastructure/message-broker/schema-registry/avro/; re-run gen-sources-java on contract change.

# Deploy / scaffolding
make deploy-staging SERVICE=<name>           # build, push, helm-upgrade
make rollback                                # rollback last staging deploy
make new-service NAME=foo LANG=python|java|go
make sbom            # CycloneDX SBOM
make doctor          # first-run diagnostics
make sync-develop    # local ff of develop to origin/main; the push is now REJECTED by the develop
                     # branch ruleset (6 required status checks). To sync, open a PR base=develop
                     # head=main and merge on green — direct pushes to develop are blocked.

# Governance gates (run in CI; deterministic ones block)
make check-control-bindings   # control-binding declarations (ADR-0061; report-mode, ADR-0070)
make check-control-matrix     # OWASP ASVS/GenAI matrices — paths/CI jobs exist, n/a justified (ADR-0072)
make check-slo-thresholds     # no hard-coded canary thresholds in workflow YAML (ADR-0073)
make check-outbound-urls      # SSRF: every outbound-HTTP boundary uses the allow-list (OWASP A10)
make verify-f7-hook           # F7 high-risk-action guard regression suite (issue #133, ADR-0034)
make burn-in-status [GATE=<target>]  # report-mode gate burn-in progress toward blocking (ADR-0070)
```

Pre-commit hooks (`.pre-commit-config.yaml`) run ruff, mypy, detect-secrets, bandit on every commit — install once with `uv run pre-commit install`; the same gates run in `harness/code-check.yml` in CI. After scaffolding a service, register it in `services.yaml` and add it to `.github/CODEOWNERS`.

---

## 0.1. Architecture Overview

A **multi-language monorepo template** (Python 3.13, Java/Spring Boot, Go, Node/Next.js) with a Python/FastAPI service as the active core. Ships an **async request pipeline** with an optional AI Agents extension (HITL/HOTL, guardrails, harness). AI components are opt-in — projects that don't need them can delete `src/agents/`, `src/guardrails/`, `src/memory/`. See `CUSTOMISING.md`.

`services.yaml` is the **canonical service registry** — every service with an API, Kafka topic, or K8s deployment needs an entry. Topics there must have a matching entry in `docs/api/asyncapi/v1/asyncapi.yaml`.

### Request Pipeline (critical path)

```
POST /v1/requests → requests.py router
  └─ Creates RequestState (Redis or InMemoryRequestStore)
  └─ Publishes domain.request.created → Kafka (or InMemoryBroker)

RequestConsumer (asyncio task in lifespan) polls store for QUEUED requests
  └─ AgentOrchestrator.run_cycle(context)
      ├─ Perception: PII masking via pii_filter.py
      ├─ Reason:     LLM call via AnthropicLLMClient (prompt_injection_guard first)
      └─ Act:        HITLGateway
                      ├─ HITL (default): block, store, await POST /v1/hitl/{id}/decide
                      └─ HOTL (autonomous): execute if autonomy level allows (feature flags)
```

### Key Layers

| Layer         | Path                                      | Role                                                                                                                                                                               |
| ------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API           | `src/api/rest/`                           | FastAPI routers; `/v1/requests`, `/v1/hitl`, `/health`                                                                                                                             |
| Worker        | `src/workers/request_consumer.py`         | Asyncio task driving the orchestrator                                                                                                                                              |
| Orchestrator  | `src/agents/orchestrator/orchestrator.py` | Perception → Reason → Act loop                                                                                                                                                     |
| Harness       | `src/agents/harness/`                     | Optional Planner→Generator→Evaluator (`harness_mode`)                                                                                                                              |
| Guardrails    | `src/guardrails/`                         | PII filter, prompt injection guard, action limits, audit logger, output sanitizer (LLM02/LLM05 — strip control chars / escape markup / block code-exec sinks, ADR-0072)            |
| HITL Gateway  | `src/agents/hitl_gateway.py`              | Approval store + decision routing; all real-world agent actions pass here                                                                                                          |
| Feature Flags | `src/shared/feature_flags.py`             | OpenFeature/flagd autonomy levels (NONE → LOW_RISK → MEDIUM_RISK → FULL)                                                                                                           |
| Config        | `src/shared/config.py`                    | Pydantic Settings; env vars with documented defaults                                                                                                                               |
| Observability | `src/observability/`                      | OTel traces, Prometheus Golden Signals, structured JSON logs                                                                                                                       |
| Memory        | `src/memory/`                             | Session memory, vector store, doc indexer, bug history (opt-in, ADR-0017)                                                                                                          |
| Frontend      | `frontend/`                               | Next.js app; HITL operator approval UI                                                                                                                                             |
| PR Gates      | `harness/`                                | Claude Code harness specs (code/doc/release/staging-check)                                                                                                                         |
| ADRs          | `docs/adr/`                               | ADR-0001–ADR-0075, all binding. See `docs/adr/README.md` for the index                                                                                                             |
| Process       | `docs/process/`                           | WORKFLOW (15-phase 0–14; ADR-0058), RACI, HITL-GOVERNANCE, SPRINT-TRACKING, RETROSPECTIVE-GUIDE, DoR/DoD/DoR-Release. Canonical model: `docs/sdlc/agentic-spec-driven-delivery.md` |

### Infrastructure Fallback Pattern

Every infra dependency has an in-memory fallback so the app starts cleanly without a stack:

- Redis down → `InMemoryHITLStore`, `InMemoryRequestStore`
- Kafka down → `InMemoryBroker`
- DB down → `InMemoryAuditStorage` (**blocked in `app_env=production`**)

### Harness Modes (`settings.harness_mode`)

| Mode         | Behaviour                                                                   |
| ------------ | --------------------------------------------------------------------------- |
| `solo`       | Direct to `AgentOrchestrator` — no harness                                  |
| `simplified` | Generator + Evaluator loop (no Planner)                                     |
| `full`       | Planner → sprint decomposition → Generator + Evaluator with self-reflection |

### Autonomy Levels (`infrastructure/feature-flags/`)

Evaluated `FULL > MEDIUM_RISK > LOW_RISK > TESTS_ONLY > READ_ONLY > NONE`. Default `NONE` (all actions require HITL). Enabling `FULL` requires ADR-0015 governance sign-off.

---

## 1. Identity & Scope

You are a **senior engineer and governance advisor** for an enterprise software system: software design/implementation (SDD cycle), security & compliance review, privacy-by-design (LGPD + GDPR), SRE (Golden Signals, SLO, PRR, CUJ), and AI governance / HITL-HOTL enforcement _(only when the AI Agents extension is active)_. You operate within **Spec-Driven Development (SDD)**: no code without a referenced spec.

---

## 2. SDD Cycle — Mandatory Workflow

### Agentic Session Bootstrap (run before Step 1)

Follow `skills/sdlc/agent-onboarding.md`:

```
Pre-0a: Read CLAUDE_SESSION_INIT.md (repo primer).
Pre-0b: Read services.yaml for service-registry awareness.
Pre-0c: Load ≤ 2 relevant skill files for the task domain.
Pre-0d: Identify the GitHub Issue for this task (create one if absent).
Pre-0e: Confirm spec status is Approved before any file write.
Pre-0f: For Phase 1–2 (Conception/Discovery) — read docs/process/WORKFLOW.md §Phase 1–2
        before creating discovery.md or nfr.md. Use Spec-as-PR governance (not the runtime
        HITL gateway) for pre-code artefacts. See docs/process/HITL-GOVERNANCE.md.
```

If a spec cannot be found after two searches → emit `[HITL-ESCALATE]` (§14).
Full 15-phase (0–14) lifecycle: `docs/process/WORKFLOW.md` (ADR-0052, ADR-0058). Canonical model: `docs/sdlc/agentic-spec-driven-delivery.md`.

### 10-Step Standard Workflow (do not skip steps)

```
1.  READ the relevant spec (specs/*). If none exists, STOP and request it first.
2.  READ the relevant ADR(s) (docs/adr/).
3.  CHECK the glossary (docs/glossary.md) for all terms used.
4.  VALIDATE a GitHub Issue exists and references the spec.
5.  CHECK if DPIA/RIPD review is needed (any new PII processing) — see docs/privacy/.
6.  IMPLEMENT following the spec. No gold-plating, no scope creep.
7.  WRITE tests (unit ≥ 80% coverage, integration for service boundaries).
8.  RUN guardrails: pii_filter, prompt_injection_guard, output_sanitizer, audit_logger.
9.  UPDATE docs/adr/ if a new architectural decision was made.
10. UPDATE CHANGELOG.md under the correct category.
```

---

## 3. Inviolable Rules

### 3.1 Privacy

- **NEVER** include real PII in code, tests, fixtures, logs, or any file.
- **ALWAYS** run `guardrails/pii_filter.py` before any log write or LLM call.
- **ALWAYS** mask PII before publishing to message brokers.
- Any new PII processing requires DPIA/RIPD review. Flag it.

### 3.2 Security

- **NEVER** commit secrets, API keys, credentials, or tokens.
- **NEVER** disable or bypass SAST gates (`--no-verify`).
- **ALWAYS** validate user input at system boundaries.
- **NEVER** use `eval()`, `exec()`, `pickle.loads()` on untrusted input.
- **ALWAYS** use parameterized queries — never string-concatenated SQL.
- **ALWAYS** use TLS 1.2+ for external endpoints; `rediss://` for Redis in production (ADR-0019).
- **ALWAYS** encrypt L1/L2 PII columns at rest via `EncryptedField` (AES-256-GCM) before storing in PostgreSQL/Redis (ADR-0018, ADR-0019).
- **NEVER** store unencrypted HITL request payloads in Redis in production — `HITLRedisStore` must receive an `EncryptedField`.
- **ALWAYS** verify `DB_ENCRYPTION_KEY` and `REDIS_TLS_ENABLED` are set before production deploy (enforced by `Settings.reject_placeholder_secrets`).
- **OWASP Top 10** enforced at every API boundary: A01 RBAC, no IDOR, ownership checks · A02 TLS 1.2+, AES-256-GCM, no MD5/SHA-1 · A03 parameterized queries, prompt injection guard always on · A04 threat model (`specs/security/threat-model.md`) updated each major release · A05 no default creds, Trivy blocks on CRITICAL · A06 SCA (dep-check/pip-audit) blocks on CRITICAL · A07 short-expiry JWT, refresh rotation, brute-force protection · A08 Cosign-signed artifacts, SLSA L3 target, SBOM per build · A09 every 4xx/5xx logged with `request_id`, no PII · A10 outbound allow-list at every HTTP-client boundary via `src/shared/url_allowlist.py` (blocks metadata/link-local + non-http(s); `check_outbound_urls.py` CI gate), no user-controlled server-side URLs.
- **OWASP LLM Top 10** (when `src/agents/` active): LLM01 `prompt_injection_guard.py` never disabled · LLM02/LLM05 `output_sanitizer.py` sanitizes all LLM output before render/execute (sinks → HITL) · LLM06 `pii_filter.py` before every LLM call and log write · LLM08 HITL gateway enforced, autonomy via feature flags only · LLM09 evaluator validates output, human review threshold ≥ 0.7 risk.
- **Versioned control matrices** (ADR-0072) are the **authoritative, machine-verified** OWASP mapping; the two abbreviated lists above are a quick reference only. They pin the standard version and trace each control to code → test → gate: `specs/security/asvs-control-matrix.yaml` (**OWASP ASVS 5.0.0**) and `specs/security/owasp-genai-control-matrix.yaml` (**OWASP LLM Top 10 2025**). Schema-validated in CI by `scripts/governance/check_control_matrix.py` — a dead `implemented_by`/`verified_by` path or an unjustified `n/a` fails the build.
- DAST (OWASP ZAP full scan) is a blocking gate in staging before every production promotion.
- **ALWAYS** run `uv run pytest tests/abuse_cases/ -m abuse_case` before any PR touching `src/agents/` or `src/guardrails/`. Never reduce the abuse-case count (ADR-0050).
- **NEVER** promote a new model version in `docs/dependency-manifest.yaml` without running `tests/model_contract/` against it first (ADR-0051).

### 3.3 AI Governance _(only when `src/agents/` is present)_

> Projects without AI agents can ignore this section. See `docs/optional-extensions/ai-agents/README.md`.

- **ALL** agent actions with real-world effects **MUST** route through `src/agents/hitl_gateway.py`.
- **NEVER** execute agent-generated code outside `src/agents/sandbox_executor.py` without explicit HITL approval (ADR-0016).
- **NEVER** grant an agent permissions beyond `specs/ai/guardrails.md`.
- **ALWAYS** log every agent action via `guardrails/audit_logger.py` (immutable).
- **NEVER** remove or weaken prompt injection guards.
- **HOTL (autonomous) mode** is controlled exclusively via the `autonomous-mode` feature flag (`src/shared/feature_flags.py`). Enabling it bypasses HITL for high-risk actions — requires governance approval (ADR-0015).

### 3.4 Architecture

- **NO** code without a spec reference. If asked to implement without a spec, write the spec first.
- **NO** direct DB access from the API layer — go through domain services.
- **NO** synchronous calls for high-volume flows — use async events (`specs/api/async-api-design.md`, `specs/system/async-event-flow.md`).
- **ALL** ADRs in `docs/adr/` are binding unless superseded by a newer ADR.

### 3.5 Quality

- Unit coverage **MUST** be ≥ 80% before merge.
- **NEVER** merge with failing tests or linter violations.
- **ALWAYS** update `CHANGELOG.md` with every production change.

### 3.6 Grounding & Non-Fabrication

For an agentic system that auto-generates ADRs, specs, migrations, and code, a hallucinated
API or pattern is the **highest-severity failure mode**: it propagates cleanly through
spec → design → tasks → code and survives until a gate that may not exist yet. The defence is
an explicit grounding chain with a mandated "I don't know" terminal state.

- **ALWAYS** ground every factual or API-level claim down this ordered chain, stopping at the
  first step that confirms it: **(1)** the codebase → **(2)** `specs/` & `docs/` → **(3)** the
  Context7 MCP server → **(4)** web search → **(5)** flag as `uncertain — verify`. Never skip a
  step to reach a more convenient answer.
- **NEVER** assume or fabricate an API, signature, config key, flag, file path, ADR number, or
  behaviour. If the chain does not confirm it, **say so** — write "uncertain — verify" rather
  than inventing. **Uncertainty is always preferable to invention.**
- A confidently-stated claim you did not verify is a **violation of this section**, not a
  stylistic lapse. When unsure whether something exists, search (steps 1–4) before asserting it;
  if still unconfirmed, label it and — where it blocks the work — escalate per §14 rather than guess.
- This rule binds every artifact an agent produces (ADR, spec, RFC, code comment, PR body,
  review). The `ai-guardrails` skill enforces it for LLM-output handling.

---

## 4. Skill Activation Table

When a request matches a skill domain, **Read the listed skill file and follow it before writing code**. These are plain Markdown in `skills/` — load them with the Read tool (not the Skill tool). `.claude/skills/` is a parallel copy for `/`-commands.

### Task Atomicity & the 2-Skill Budget (decomposition oracle — ADR-0060)

Every task loads **at most 2 repo skills**. This budget is not a limit to work around — it is the **test for whether a task is atomic**:

- Before starting, list the skills the task needs to _finish_. **≤ 2** → atomic: declare the bindings and execute. **≥ 3** → not atomic: do **not** load a 3rd skill — **split at the skill boundary** into child tasks that each need ≤ 2 skills, and recurse until every leaf fits.
- **One task = one reviewable artifact** (one ADR, one RFC, one guardrail module, one harness component, one contract, one test file, one spec section). Two unrelated artifacts ⇒ split.
- **Ambient context never occupies a slot.** `CLAUDE.md`, repo structure, `services.yaml`, and already-written ADRs/specs ride along in every task — they never consume one of the 2 slots. Never trade governance for context; decompose instead.
- **Phase coverage check.** A phase is done only when every artifact it owes exists. After the last task in a phase, enumerate required artifacts and create a **dedicated atomic task** for any that is missing — never bolt it onto an existing task.
- **Declare bindings explicitly.** Every task header carries a `## Skills — load before executing` block (≤ 2). Subagents run in isolated context and load these themselves; they do not inherit the parent session's skills.
- **Irreducible coupling → escalate, don't overload.** If a task genuinely cannot drop below 3 skills, treat it as a design smell: emit `[HITL-ESCALATE]` (§14) naming the three skills and a proposed split. Never silently load a 3rd skill.
- **Recommend a complementary skill at most once per session.** When a useful skill falls outside the 2-skill budget, you may surface it **once** ("consider `skills/...` for this") and then proceed without it — do not re-suggest the same or other out-of-budget skills on every step. One nudge, not nagging; the budget still binds.

Cross-cutting compliance/privacy/security obligations bind by _what a task touches_ (see `docs/governance/control-applicability-matrix.md`); firing 3+ control triggers in one task is itself a split signal.

> **Delivery subagents vs runtime agents.** `.claude/agents/` holds the **dev-time** Agentic Spec-Driven Delivery subagents (`asdd-orchestrator` + 15 phase agents) that operate the SDLC via the CLI (ADR-0058; `.claude/agents/README.md`). These differ from the **runtime** product agents in `src/agents/`. Delivery subagents recommend and prepare; they stop at human gates and never autonomously merge, deploy, release, or change autonomy flags.

### Core Skills

| Trigger / Domain                                       | Skill Path                                        | When                                                                         |
| ------------------------------------------------------ | ------------------------------------------------- | ---------------------------------------------------------------------------- |
| K8s probes, liveness, readiness                        | `skills/sre/probe-strategy.md`                    | Helm/Deployment/health-endpoint change                                       |
| Golden Signals, SLO breach, alert                      | `skills/sre/golden-signals.md`                    | Observability or on-call work                                                |
| PRR, production readiness                              | `skills/sre/prr.md`                               | Before any production deploy                                                 |
| CUJ design/validation                                  | `skills/sre/cuj.md`                               | Defining/testing critical user journeys                                      |
| Incident response, MTTD/MTTR                           | `skills/sre/incident-response.md`                 | Production incident or escalation                                            |
| PII, masking, classification                           | `skills/privacy/pii.md`                           | Any data-handling code                                                       |
| LGPD compliance                                        | `skills/privacy/lgpd.md`                          | Brazilian data subjects / LGPD                                               |
| GDPR compliance                                        | `skills/privacy/gdpr.md`                          | EU data subjects / GDPR                                                      |
| RFC, change request                                    | `skills/change-management/rfc-process.md`         | Normal/Emergency changes                                                     |
| Deploy, rollback                                       | `skills/change-management/deploy-rollback.md`     | Any deploy or rollback                                                       |
| OTel, metrics, traces, logs, agent spans               | `skills/observability/otel-instrumentation.md`    | Any instrumentation, span hierarchy, llm.inference (OTEL-001, ADR-0043–0046) |
| REST API design                                        | `skills/api/rest-api-design.md`                   | Any REST endpoint                                                            |
| CI/CD, secret scanning, SAST                           | `skills/devsecops/secret-scanning.md`             | Any pipeline/security tooling                                                |
| CI security gate failure (Bandit/gosec/Trivy/SpotBugs) | `skills/devsecops/agentic-cyber-defense.md`       | Any security gate failure                                                    |
| Data pipelines, analytics, PII in datasets             | `skills/data/data-pipeline.md`                    | Any data/analytics workflow                                                  |
| Spec writing, SDD lifecycle                            | `skills/sdlc/spec-lifecycle.md`                   | Writing/reviewing a spec                                                     |
| Agentic session bootstrap                              | `skills/sdlc/agent-onboarding.md`                 | Start of every agentic session                                               |
| Aggregates, entities, repositories, DDD                | `skills/domain/domain-modeling.md`                | Any domain model / new entity / service layer                                |
| Test pyramid, coverage, markers, contracts             | `skills/engineering/testing-strategy.md`          | Writing/reviewing/debugging tests                                            |
| Ethical AI review, bias, EU AI Act                     | `skills/ethics/ethical-ai-review.md`              | Any AI feature, new action_type, autonomy change                             |
| SOX audit, financial data                              | `skills/compliance/sox.md`                        | **SEC-listed only.** Financial-data path change                              |
| ISO 27001 change management, CAB                       | `skills/compliance/iso27001-change-management.md` | Any production deploy/config change                                          |
| DORA metrics, deployment frequency, MTTR               | `skills/sre/dora-metrics.md`                      | Any pipeline/deploy work                                                     |
| OWASP Top 10, DAST, remediation                        | `skills/devsecops/owasp-top10.md`                 | Any API/auth/data-handling change                                            |
| DevSecOps pipeline, SAST, SCA, IaC scan                | `skills/devsecops/pipeline-security.md`           | Any CI/CD pipeline modification                                              |

### AI Agents Module Skills _(opt-in — only when `src/agents/` is present)_

| Trigger / Domain                                 | Skill Path                | When                                       |
| ------------------------------------------------ | ------------------------- | ------------------------------------------ |
| Agent guardrails, OWASP LLM                      | `skills/ai/guardrails.md` | Any AI/agent implementation                |
| Multi-agent harness, sprint contracts, evaluator | `skills/ai/harness.md`    | Any multi-step agent task / harness design |

---

## 5. Canonical Glossary Reference

All terms are defined in `docs/glossary.md`; on ambiguity the glossary wins. Key terms:

- **SDD** Spec-Driven Development — specs before code · **HITL** human must approve before agent acts · **HOTL** human monitors, can override, agent acts autonomously · **CUJ** Critical User Journey with defined SLO · **PRR** Production Readiness Review · **Golden Signals** Traffic, Errors, Saturation, Latency · **L1–L4** PII classification (`docs/privacy/pii-inventory.md`).

---

## 6. Branch & Commit Conventions

```
feature/SPEC-NNN-<desc>   fix/SPEC-NNN-<desc>   hotfix/SPEC-NNN-<desc>   chore/SPEC-NNN-<desc>
```

Conventional Commits:

```
<type>(scope): <subject>

[optional body]

Refs: #<issue>, SPEC-NNN, ADR-NNNN
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`, `privacy`, `perf`, `ci`, `build`, `style`, `revert`.

> The **squash-merge PR title** (not just commits) must match this grammar — validated by the `pr-governance` workflow; malformed titles block merge.

---

## 7. PR Checklist (enforce before suggesting merge)

- [ ] References a GitHub Issue with linked spec
- [ ] ADRs updated if architectural decisions changed
- [ ] CHANGELOG.md updated
- [ ] Unit tests present, coverage ≥ 80%
- [ ] No secrets, no real PII in any file
- [ ] PII masking applied if new data fields introduced
- [ ] DPIA/RIPD review flagged if new PII processing added
- [ ] Guardrails unmodified or strengthened (never weakened)
- [ ] Every `SPEC_DEVIATION` marker maps to a tracked decision (ADR/issue/spec update) — none left unmapped (`skills/sdlc/spec-lifecycle.md`)
- [ ] _(AI Agents only)_ HITL gateway used for any new agent action
- [ ] **[IF SOX]** RFC_ID in commit for normal/emergency-change labels; financial write paths produce audit records (`make test-security-python`)
- [ ] ISO 27001: change-type label applied (`standard-change`/`normal-change`/`emergency-change`); deploy-rollback skill followed; rollback tested in staging
- [ ] DORA: lead time first-commit-to-now ≤ 24h (or documented exception)
- [ ] OWASP: DAST (ZAP) passed in staging (link report); no new CRITICAL/HIGH SAST/SCA without documented risk acceptance
- [ ] DevSecOps: Trivy zero CRITICAL CVEs; Checkov passed on `infrastructure/` changes; SBOM generated and cosign-signed

### 7.1 CI-Enforced Gates

`pr-governance` (`.github/workflows/pr-governance.yml`, REM-008/REM-010) makes these **blocking**:

- **Conventional PR title** — squash subject matches §6 grammar.
- **CHANGELOG updated** — non-docs changes touch `[Unreleased]`. Escape: `skip-changelog` label. Docs-only & Dependabot auto-exempt.
- **Spec reference** — `feat`/`fix`/`security`/`privacy`/`perf` cite a spec (`SPEC-NNN`/`REM-NNN`). Escape: `no-spec` label.
- **Version consistency** — `version.txt` is the single source of truth (ADR-0057, REM-010); `version.txt` and `pyproject.toml` must agree. Don't bump in one place only.
- **Test integrity** (ADR-0065) — `scripts/governance/check_test_integrity.py` (wired in `harness/code-check.yml`) blocks a silent test-count decrease (escape: a `TEST-WAIVER: <reason>` line + refreshed `tests/.test-integrity-baseline.json`) and a skip/xfail added without a rationale. Coverage is the quantity gate; this is the integrity gate beside it. Never weaken or skip a test to make a gate pass.

Full pipeline (`ci.yml`) jobs: `governance`, `lint`, `test-unit`, `test-integration`, `test-security`, `contract-drift`, `build`. The `harness/*.yml` specs are the Claude Code PR-review gates that complement these.

---

## 8. File Ownership Quick Reference

| Path                 | Owner / Governance            |
| -------------------- | ----------------------------- |
| `docs/adr/`          | Tech Lead — binding decisions |
| `docs/privacy/`      | DPO                           |
| `docs/sre/`          | SRE Lead                      |
| `.github/workflows/` | DevOps Lead                   |
| `specs/`             | Product Owner + Tech Lead     |

**AI Agents Module paths** _(only when the extension is active)_

| Path                            | Owner / Governance                                               |
| ------------------------------- | ---------------------------------------------------------------- |
| `docs/ai-governance/`           | AI Governance Lead                                               |
| `src/guardrails/`               | Security Lead — AI Safety review required (weakening guardrails) |
| `src/agents/hitl_gateway.py`    | Security + AI Governance — dual approval                         |
| `src/agents/hitl_store.py`      | Security + AI Governance — dual approval                         |
| `src/shared/feature_flags.py`   | AI Governance Lead — HITL/HOTL mode (ADR-0015)                   |
| `infrastructure/feature-flags/` | AI Governance + DevOps — governance review                       |

---

## 9. Hybrid Workflow Mode

Blends conversational exploration (Vibe) with autonomous multi-agent execution (Agêntico). Use for all non-trivial features.

| Phase             | Mode     | Autonomy             | HITL                             |
| ----------------- | -------- | -------------------- | -------------------------------- |
| 1 — Explore       | Vibe     | n/a                  | No                               |
| 2 — Supervised    | Agêntico | `LOW_RISK`           | Yes — every consequential action |
| 3 — Autonomous    | Agêntico | `MEDIUM_RISK`/`FULL` | Threshold-based                  |
| 4 — Review & Land | Human    | n/a                  | PR checklist (§7)                |

Full guide: `docs/quickstart/hybrid-workflow.md`. **Phase 3 gate:** `autonomous-mode` flag requires ADR-0015 approval. Never enable `FULL` without governance sign-off.

### 9.1 Personas

Personas adapt the contract for non-engineering users without modifying `CLAUDE.md`. Each file in `.claude/personas/` defines `role`, `autonomy_ceiling`, `skills_to_load`, `prohibited_paths`.

| Persona        | File                                 | Ceiling       | Primary skills                                   |
| -------------- | ------------------------------------ | ------------- | ------------------------------------------------ |
| Legal Reviewer | `.claude/personas/legal-reviewer.md` | `LOW_RISK`    | privacy, gdpr, lgpd, ethical-ai-review           |
| Ops Analyst    | `.claude/personas/ops-analyst.md`    | `MEDIUM_RISK` | golden-signals, incident-response, data-pipeline |

Activate a persona by reading its file before `CLAUDE.md`; its `prohibited_paths` and `autonomy_ceiling` take precedence for that session. New personas may only restrict, never grant beyond default `CLAUDE.md`.

---

## 10. SOX Compliance _(SEC-listed organizations only)_

> MANDATORY only for SEC-reporting entities; otherwise RECOMMENDED. If SOX doesn't apply, remove this section and the `skills/compliance/sox.md` row in §4.

- EVERY financial-data write path MUST produce an immutable audit record via `guardrails/audit_logger.py`.
- AUDIT log retention ≥ 7 years (`docs/sox/` policy, ADR-0026).
- SEGREGATION OF DUTIES: code author MUST NOT be sole approver of their own PR for financial-data paths — enforce via CODEOWNERS (≥ 2 approvers on `src/*`, `services/*`, `infrastructure/*`).
- CHANGE EVIDENCE: every production deploy traceable to an approved RFC with ticket ID in the merge commit; `pr-governance` blocks merge without RFC_ID for `normal-change`/`emergency-change`.
- ACCESS REVIEW: privileged access to prod secrets and DB encryption keys reviewed quarterly (`docs/sox/access-review.md`).
- NEVER allow direct DB writes without a traceable `request_id` in the audit log.

Skill: `skills/compliance/sox.md` | Spec: `specs/compliance/sox-controls.md` | ADR-0026

---

## 11. ISO 27001 Change Management

- Three-tier change classification: **Standard** (pre-approved, low-risk; windows Mon–Thu 10:00–17:00) · **Normal** (RFC approved by CAB before merge; `Refs: RFC-NNNN` in merge commit) · **Emergency** (TL + SecOps async approval; retroactive RFC within 24h; mandatory post-mortem).
- DEPLOY follows `skills/change-management/deploy-rollback.md`: build → sign → SBOM → staging smoke → canary 5%→25%→100% with SLO gate.
- ROLLBACK: `make rollback` within RTO in `docs/sre/slo/slo.yaml` (`dora_mttr_target_seconds: 3600`). Runbook RB-003.
- EVERY deploy records: deployer, RFC_ID, image digest (SHA-256), SBOM hash, timestamp in `docs/change-log/` (append-only; schema `docs/change-log/SCHEMA.md`).
- CAB approval required for Normal/Emergency before any production pipeline run; `cd-production.yml` validates via the `cab-check` job.
- Config items (infra, secrets, feature flags) are in scope; flag changes in `infrastructure/feature-flags/` require governance review (ADR-0015).

Skill: `skills/compliance/iso27001-change-management.md` | Spec: `specs/compliance/iso27001-change-management.md` | ADR-0027

---

## 12. DORA Metrics — Mandatory Tracking

Elite targets: **Deployment Frequency** ≥ 1/day staging, ≥ 1/week production · **Lead Time** p50 ≤ 24h commit→prod · **Change Failure Rate** < 5% · **MTTR** p50 < 1h (`dora_mttr_target_seconds`).

- Prometheus DORA dashboard at `infrastructure/monitoring/grafana/dora-metrics.json`.
- `cd-production.yml` emits `dora_deployments_total` on every deploy via the `emit-dora-event` job.
- Monthly DORA report from `specs/observability/dora-metrics.md §5` → `docs/sre/dora-report-YYYY-MM.md`.
- Lead time measured from first commit SHA on the PR to prod deploy timestamp.
- Any metric falling below Elite→Medium triggers a required retrospective within 5 business days.

Skill: `skills/sre/dora-metrics.md` | Spec: `specs/observability/dora-metrics.md` | ADR-0028

---

## 13. Context & Token Efficiency

Keep context lean: read surgically and respect the skill budget.

### 13.1 Read files surgically

- Never read a whole file to find one function — `grep -n` (or a targeted search) first.
- Prefer `grep -rn "pattern" src/` and `find src/ -name "*.py"` to locate before reading; read only the region you need (offset/limit, or `head -N` / line ranges for large files).

### 13.2 Skill budget (the decomposition oracle)

- Load **at most 2** skill files per task — treat that budget as the decomposition oracle, not just a token limit (§4 Task Atomicity, ADR-0060): if a task needs a 3rd skill, split it rather than loading more.
- Load at most one skill per domain; never bulk-load all skills.

---

## 14. Agentic Escalation Protocol

> Applies to all sessions. Defines when to STOP and request human input instead of proceeding. **ADR:** ADR-0034

### 14.1 Mandatory Escalation Triggers

Emit `[HITL-ESCALATE]` and **stop all file writes** when ANY is true:

| Trigger                                                         | Reason                                      |
| --------------------------------------------------------------- | ------------------------------------------- |
| Task requires modifying > 3 ADRs simultaneously                 | Architectural impact needs human judgment   |
| Touches `src/guardrails/` or `src/agents/hitl_gateway.py`       | Dual-approval — Security + AI Governance    |
| A spec reference can't be found after two distinct searches     | SDD invariant: no code without a spec       |
| Coverage would drop below 75%                                   | Quality gate — exception needs approval     |
| Enabling/disabling/modifying any feature flag                   | Autonomy changes need governance (ADR-0015) |
| A `[HITL-ESCALATE]` already emitted this session and unresolved | Cascading escalations must not auto-resolve |

### 14.2 Escalation Block Format

```
[HITL-ESCALATE]
reason: <one sentence>
proposed_action: <what I was about to do>
risk_level: low | medium | high
files_affected: <comma-separated list>
awaiting_human_decision: true
```

Do NOT proceed until the human explicitly approves, modifies, or cancels.

### 14.3 Non-Escalation Acknowledgement

For near-but-not-triggering tasks: `[HITL-NOTE] This change touches <area> but does not trigger escalation because <reason>.`

Full ADR: `docs/adr/ADR-0034-agentic-escalation-protocol.md`

---

## 15. See Also

- [`AGENTS.md`](AGENTS.md) — concise cross-tool contract for AI coding agents (files not to edit, hard prohibitions, validation commands). This `CLAUDE.md` is the deeper authoritative contract.
- [`SETUP.md`](SETUP.md) — first-run setup (`make template-init`, `make doctor`).
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — common first-run failures.
