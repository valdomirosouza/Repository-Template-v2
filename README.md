# Enterprise Monorepo Template

> Production-ready monorepo template for enterprise software systems. AI/agent capabilities are optional opt-in extensions.
> **Version:** 2.20.0 | **Status:** Active | **License:** MIT

[![CI](https://github.com/valdomirosouza/Repository-Template-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/valdomirosouza/Repository-Template-v2/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/valdomirosouza/Repository-Template-v2)](https://github.com/valdomirosouza/Repository-Template-v2/releases/latest)

---

## Who is this for?

| You are…                  | Start with                         | Stack                                                         |
| ------------------------- | ---------------------------------- | ------------------------------------------------------------- |
| Solo dev / research / PoC | **Minimal** — `make setup-minimal` | Python + unit tests, no Docker                                |
| Product team              | **Core** — `make setup-core`       | + PostgreSQL · Redis · OTel · Prometheus · Grafana · Jaeger   |
| Regulated team / AI SDLC  | **Enterprise** — `make setup-full` | + Kafka · Schema Registry · flagd · full HITL/HOTL governance |

## Choose your adoption profile

| Command              | Audience        | Brings up                                         |
| -------------------- | --------------- | ------------------------------------------------- |
| `make setup-minimal` | Solo / PoC      | Python deps + unit tests (no Docker)              |
| `make setup-core`    | Product team    | PostgreSQL · Redis · observability stack          |
| `make setup-full`    | Enterprise / AI | Everything (adds Kafka · Schema Registry · flagd) |

## 10-minute quick start (Minimal profile)

```bash
gh repo create my-project --template valdomirosouza/Repository-Template-v2 --clone
cd my-project
make template-init PROJECT_NAME=my-project ORG=my-org REGISTRY=ghcr.io/my-org PROFILE=python-api
make doctor
make setup-minimal
make run
curl http://localhost:8000/health
```

For the Standard and Full paths, see **Standard setup** below and [`SETUP.md`](SETUP.md).
New here? Jump to [For AI coding agents](#for-ai-coding-agents) ·
[Troubleshooting](docs/troubleshooting.md).

---

## Standard setup: Clone → Initial Setup → Code

### 1. Clone

Click **"Use this template"** on the GitHub repository page, or run:

```bash
gh repo create my-project --template valdomirosouza/Repository-Template-v2 --clone
cd my-project
```

> **Devcontainer alternative** (no local tool installs): open the folder in VS Code and choose
> **Dev Containers: Reopen in Container** — Python, Java, Go, and Node are pre-configured.

---

### 2. Initial Setup

```bash
# Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY (the only always-required value).
# Generate one with: openssl rand -hex 32
# LLM_API_KEY is only needed when AI_AGENTS_ENABLED=true (AI Agents extension).

# Install Python deps, start all infrastructure containers, run DB migrations
make setup

# Confirm everything is alive
curl http://localhost:8000/health   # → {"status": "ok"}
curl http://localhost:8000/ready    # → {"status": "ready"}
```

> If `/ready` returns `503`, run `docker compose ps` — PostgreSQL or Redis may still be initialising.

**Choose your setup profile** (progressive adoption — pick the smallest that fits):

| Command              | Profile                  | Brings up                                                              |
| -------------------- | ------------------------ | ---------------------------------------------------------------------- |
| `make setup-minimal` | _none (no Docker)_       | Python deps + unit tests only — solo dev / PoC                         |
| `make setup-core`    | `core` + `observability` | PostgreSQL · Redis · OTel · Prometheus · Grafana · Jaeger              |
| `make setup-full`    | `full`                   | Everything below (adds Kafka · Schema Registry · flagd · Alertmanager) |

`make setup` is a backwards-compatible alias for `make setup-core`. After any setup,
run **`make smoke`** to validate the active profile.

**Containers by profile:**

| Container       | Port(s)     | Profile(s)                  | Role                                               |
| --------------- | ----------- | --------------------------- | -------------------------------------------------- |
| PostgreSQL      | 5432        | core · observability · full | Audit log, pgvector agent memory                   |
| Redis           | 6379        | core · observability · full | HITL store, request store, session cache           |
| OTel Collector  | 4317 (gRPC) | observability · full        | Traces, metrics, logs aggregator                   |
| Prometheus      | 9090        | observability · full        | Metrics scrape + alerting                          |
| Grafana         | 3001        | observability · full        | Dashboards — http://localhost:3001 (admin / admin) |
| Jaeger          | 16686       | observability · full        | Distributed trace UI                               |
| Kafka (KRaft)   | 9092        | events · full               | Async event broker                                 |
| Schema Registry | 8081        | events · full               | Avro schema validation                             |
| flagd           | 8013        | full                        | OpenFeature flag server                            |
| Alertmanager    | 9093        | full                        | Alert routing (PagerDuty / Slack integration)      |

> Ports are overridable via `.env` (`POSTGRES_PORT`, `GRAFANA_PORT`, …) and the stack is
> namespaced by `COMPOSE_PROJECT_NAME` so multiple clones can run side by side.

---

### 3. Code

**Verify the baseline is green:**

```bash
make test-unit-python   # fast, no Docker required — run this first
make test-python        # full suite: unit + integration + security (needs infra-up)
make lint-python        # ruff + mypy + detect-secrets
```

**Fire the full async pipeline end-to-end:**

```bash
make run &

REQUEST_ID=$(curl -s -X POST http://localhost:8000/v1/requests \
  -H "Content-Type: application/json" \
  -d '{"context": {"task": "summarise quarterly report", "source": "internal"}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['request_id'])")

curl -s http://localhost:8000/v1/requests/$REQUEST_ID | python3 -m json.tool
```

Expected: `{"status": "completed", "result": {...}, "request_id": "..."}`. If `"processing"`, retry after a second. If the LLM key is not set, the orchestrator routes to HITL — approve at `POST /v1/hitl/<id>/decide`.

**Open API docs and observability:**

```bash
open http://localhost:8000/docs    # Swagger UI (non-production only)
open http://localhost:3001         # Grafana Golden Signals (admin / admin)
open http://localhost:16686        # Jaeger trace UI
```

**Pick your language guide and start building:**

| I am building...                  | Guide                                                                    |
| --------------------------------- | ------------------------------------------------------------------------ |
| Python API or AI agent            | [`docs/quickstart/python-backend.md`](docs/quickstart/python-backend.md) |
| Java / Spring Boot domain service | [`docs/quickstart/java-backend.md`](docs/quickstart/java-backend.md)     |
| Go high-throughput worker         | [`docs/quickstart/go-backend.md`](docs/quickstart/go-backend.md)         |
| React / Next.js frontend          | [`docs/quickstart/frontend.md`](docs/quickstart/frontend.md)             |
| Scheduled job or batch processor  | [`docs/quickstart/jobs-worker.md`](docs/quickstart/jobs-worker.md)       |

Also read after your language guide:

- [`docs/quickstart/contract-driven-dev.md`](docs/quickstart/contract-driven-dev.md) — generate code from OpenAPI / AsyncAPI / proto
- [`docs/quickstart/add-new-service.md`](docs/quickstart/add-new-service.md) — 10-step checklist for registering a new service
- [`docs/quickstart/deploy-to-production.md`](docs/quickstart/deploy-to-production.md) — canary deploy, CAB approval, rollback procedure

**Minimum required customisations before committing your first feature:**

> ⚠️ **Start here → [`SETUP.md`](SETUP.md)** — three steps are enforced by CI gates and will block every PR until completed (CODEOWNERS teams, image registry, `.env` secrets).

| File                     | What to change                                                                  |
| ------------------------ | ------------------------------------------------------------------------------- |
| **`.github/CODEOWNERS`** | **Replace `@your-org/*` — CI blocks every PR until done** `[BLOCKER]`           |
| **`services.yaml`**      | **Replace `yourorg/` image registry — Helm deploy fails otherwise** `[BLOCKER]` |
| **`.env`**               | **Set `[REQUIRED]` secrets — app refuses to start in prod** `[BLOCKER]`         |
| `version.txt`            | Reset to `0.1.0`                                                                |
| `.env.example`           | Add project-specific environment variables                                      |
| `docs/adr/`              | Add ADRs for your own architectural decisions                                   |
| `specs/`                 | Write specs for features before implementing                                    |
| `CLAUDE.md`              | Adjust AI behavioural contract for your team                                    |

> For term definitions (SDD, HITL/HOTL, CUJ, PRR) see [`docs/glossary.md`](docs/glossary.md).

> See [`CUSTOMISING.md`](CUSTOMISING.md) for the full adoption guide, including what to delete if
> you don't need Java, Go, frontend, AI agents, or Terraform.

> For architecture details see [`docs/architecture.md`](docs/architecture.md) and [`CLAUDE.md`](CLAUDE.md).

---

## What you get

A production-ready scaffold for enterprise teams. Everything is wired together from day one:

| Layer                    | What's included                                                                                                                                                                                                                                                              |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Languages**            | Python 3.13 · Java 21 · Go 1.24 · Node 22 / Next.js 15                                                                                                                                                                                                                       |
| **Service scaffolds**    | `services/domain-service/` (Spring Boot) · `services/event-worker/` (Go) · `frontend/web/`                                                                                                                                                                                   |
| **Infrastructure**       | PostgreSQL · Redis · Kafka (KRaft) · Schema Registry · flagd                                                                                                                                                                                                                 |
| **IaC**                  | Helm chart for Kubernetes · Terraform modules for VPC, EKS, and ElastiCache Redis                                                                                                                                                                                            |
| **Observability**        | OpenTelemetry · Prometheus · Grafana (Golden Signals + CUJ) · Jaeger (with sampling policy)                                                                                                                                                                                  |
| **Alerting**             | Golden Signals rules + 14 agent-specific alert rules (HITL, feedback loop, MTTD/MTTR, LLM cost)                                                                                                                                                                              |
| **Governance**           | 21 ADRs · SDD cycle · STRIDE threat model · privacy-by-design (LGPD + GDPR) · PRR checklist                                                                                                                                                                                  |
| **Specs**                | System · AI/agents · Privacy · Security (STRIDE) · Ethics (EU AI Act) · SDLC lifecycle                                                                                                                                                                                       |
| **CI/CD**                | GitHub Actions for Python · Java · Go · Frontend · AI-Safety — all path-filtered · canary CD with SLO gates                                                                                                                                                                  |
| **Testing**              | Unit · Integration · Security · Chaos · Contract tests (harness message schema invariants)                                                                                                                                                                                   |
| **Dev experience**       | Devcontainer · `docker compose up -d` · per-language `make` targets · skills catalog                                                                                                                                                                                         |
| **AI/Agents** _(opt-in)_ | Anthropic Claude · HITL/HOTL gateway · multi-agent harness (Planner/Generator/Evaluator) · guardrails · ethical AI · feedback learner (Learn stage) · governed tool registry · context graph (autonomy tier) · agentic maturity self-assessment · governance gate · personas |

---

## Daily workflow

```bash
# Python (API gateway + AI agents)
make test-python          # unit + integration (coverage ≥ 80%)
make lint-python          # ruff + mypy + detect-secrets
make run                  # FastAPI dev server with hot-reload

# Java (domain service)
make test-java SERVICE=domain-service
make lint-java SERVICE=domain-service
make run-java  SERVICE=domain-service

# Go (event worker)
make test-go   SERVICE=event-worker
make lint-go   SERVICE=event-worker
make run-go    SERVICE=event-worker

# Frontend
make test-frontend APP=frontend
make lint-frontend APP=frontend
make run-frontend  APP=frontend

# Infrastructure
make infra-up          # start full dev stack
make infra-down        # stop (preserves volumes)
make infra-reset       # stop + wipe all volumes
make test-infra-up     # start lightweight test stack (offset ports)

# Database
uv run alembic upgrade head                          # apply migrations
uv run alembic revision --autogenerate -m "message"  # generate new migration

# Contracts
make openapi-ui        # Swagger UI at http://localhost:8082
make asyncapi-ui       # AsyncAPI Studio at http://localhost:8083
make gen-api-client-ts # regenerate TypeScript client from OpenAPI
make gen-proto-go      # regenerate Go gRPC stubs from proto

# Deploy
make deploy-staging SERVICE=api-gateway VERSION=x.y.z
make rollback

# Scaffold a new service (REGISTER=true also updates services.yaml + CODEOWNERS + Prometheus)
make new-service NAME=my-service LANG=python OWNER=platform PORT=8020 REGISTER=true
```

> See [`scaffold/README.md`](scaffold/README.md) for templates, flags, and per-language file trees.

---

## Repository Structure

```
.
├── CLAUDE.md                    ← AI behavioral contract (v2.7.0)
├── services.yaml                ← Service catalog (all languages, ports, topics)
├── docker-compose.yml           ← Full dev infrastructure stack
├── docker-compose.test.yml      ← Lightweight test stack (offset ports)
├── .devcontainer/               ← Multi-language devcontainer (Python+Java+Go+Node)
│
├── docs/
│   ├── quickstart/              ← Role-specific onboarding guides (5 languages)
│   ├── adr/                     ← Architecture Decision Records (ADR-0001–0041)
│   ├── api/                     ← OpenAPI · AsyncAPI · gRPC proto contracts
│   ├── privacy/                 ← PII inventory, DPIA/RIPD, data retention
│   ├── sre/                     ← SLOs, error budget policy, PRR, CUJ, FinOps, capacity planning
│   ├── runbooks/                ← RB-003 HITL recovery + rollback + DR
│   ├── governance/              ← Team topology, RACI matrix, owner onboarding
│   ├── ai-governance/           ← Model card, EU AI Act, NIST AI RMF
│   └── dependency-manifest.yaml ← AI model versions, cost rates, governance metadata
│
├── specs/                       ← Spec-Driven Development specs (write before code)
│   ├── system/                  ← Vision, architecture, async event flow
│   ├── ai/                      ← Agent design, HITL/HOTL, guardrails, harness
│   ├── privacy/                 ← PII, retention, DPIA/RIPD
│   ├── security/                ← STRIDE threat model
│   ├── ethics/                  ← Ethical AI principles (EU AI Act mapping)
│   └── sdlc/                    ← Development lifecycle (5-stage with gate criteria)
│
├── src/                         ← Python application code
│   ├── agents/
│   │   ├── hitl_gateway.py      ← HITL approval gateway (all agent actions)
│   │   ├── hitl_store.py        ← Pluggable HITL persistence (Memory / Redis)
│   │   ├── orchestrator/        ← Perception → Reason → Act loop
│   │   └── harness/             ← Multi-agent harness (Planner/Generator/Evaluator)
│   ├── api/rest/                ← FastAPI routers, middleware, lifespan
│   ├── guardrails/              ← PII filter, injection guard, audit logger, limits
│   ├── observability/           ← OTel setup, Prometheus metrics, structured logger
│   └── shared/                  ← Config, models, retry, DB pool, feature flags
│
├── services/
│   ├── domain-service/          ← Java 21 / Spring Boot 3.4 — CRUD API + Kafka consumer
│   └── event-worker/            ← Go 1.24 — stateless Kafka consumer
│
├── frontend/
│   └── frontend/                ← Next.js 15 / TypeScript — HITL approval UI
│
├── infrastructure/
│   ├── helm/api-gateway/        ← Helm chart (Deployment · HPA · PDB · Ingress)
│   ├── terraform/
│   │   ├── modules/networking/  ← VPC, subnets, NAT GW, security groups (AWS)
│   │   ├── modules/kubernetes/  ← EKS cluster with KMS encryption
│   │   ├── modules/cache/       ← ElastiCache Redis with TLS + at-rest encryption
│   │   └── environments/        ← staging/ and production/ root modules
│   ├── k8s/                     ← Static manifests (Deployment · Service · HPA · PDB)
│   ├── feature-flags/           ← flagd + autonomous-mode.yaml (OpenFeature)
│   └── monitoring/
│       ├── prometheus/rules/    ← golden-signals.yaml + agent-alerts.yaml (14 rules)
│       ├── grafana/             ← 5 dashboards (Golden Signals · SRE · Agent · CUJ)
│       └── jaeger/              ← Collector config + per-service sampling strategy
│
├── tests/
│   ├── unit/                    ← Fast, no I/O — all modules covered
│   ├── integration/             ← Real services (Postgres, Redis, Kafka)
│   ├── contract/                ← Harness message schema invariants (32 tests)
│   ├── security/                ← OWASP LLM Top 10 + PII leakage
│   └── chaos/experiments/       ← 8 fault-injection scenarios
│
├── .github/workflows/           ← CI: Python · Java · Go · Frontend · AI-Safety (path-filtered)
│                                   CD: staging (auto) · production (canary, manual)
└── skills/                      ← Claude Code enterprise skills catalog
    ├── sre/                     ← golden-signals · prr · cuj · incident-response · capacity-planning
    ├── privacy/                 ← pii · lgpd · gdpr · data-subject-rights
    ├── change-management/       ← rfc-process · deploy-rollback · cab-process
    ├── ai/                      ← guardrails · harness
    ├── observability/           ← otel-instrumentation
    ├── api/                     ← rest-api-design
    ├── devsecops/               ← secret-scanning
    └── sdlc/                    ← spec-lifecycle
```

Full annotated tree: [`docs/repo-structure.md`](docs/repo-structure.md)

---

## API Contracts

| Type   | Spec                                                                                   | Description                            |
| ------ | -------------------------------------------------------------------------------------- | -------------------------------------- |
| REST   | [`docs/api/openapi/v1/openapi.yaml`](docs/api/openapi/v1/openapi.yaml)                 | Synchronous REST API (OpenAPI 3.1)     |
| Events | [`docs/api/asyncapi/v1/asyncapi.yaml`](docs/api/asyncapi/v1/asyncapi.yaml)             | Kafka event contracts (AsyncAPI 2.6)   |
| gRPC   | [`docs/api/grpc/proto/ai_service.proto`](docs/api/grpc/proto/ai_service.proto)         | Inter-service calls (Protocol Buffers) |
| Agents | [`infrastructure/proto/harness_state.proto`](infrastructure/proto/harness_state.proto) | Harness state + HITL + audit messages  |

> **Rule:** Never write stubs by hand. Generate from the contracts — see [`docs/quickstart/contract-driven-dev.md`](docs/quickstart/contract-driven-dev.md).

---

## Observability

| Signal                   | Stack                            | Location                                                         |
| ------------------------ | -------------------------------- | ---------------------------------------------------------------- |
| Metrics (Golden Signals) | Prometheus + Grafana             | http://localhost:3001 (admin/admin)                              |
| Traces                   | OpenTelemetry + Jaeger           | http://localhost:16686                                           |
| Logs                     | Structured JSON + OTel Collector | —                                                                |
| SLO / Error Budget       | Prometheus + Grafana             | `sre-overview.json` dashboard                                    |
| CUJ-001 dashboard        | Prometheus + Grafana             | `cuj-dashboards/CUJ-001-*.json`                                  |
| Golden Signals alerts    | PrometheusRule                   | `infrastructure/monitoring/prometheus/rules/golden-signals.yaml` |
| Agent-specific alerts    | PrometheusRule                   | `infrastructure/monitoring/prometheus/rules/agent-alerts.yaml`   |

Agent alerts cover: HITL queue depth / rejection rate / wait time, feedback loop bias, MTTD/MTTR SLOs, autonomous resolution rate, LLM token budget, and DLQ growth.

All dashboards and datasources are **provisioned automatically** — no manual import needed after `make infra-up`.

Jaeger sampling policy: HITL and request submission endpoints sampled at 100%; health and metrics probes excluded. See [`infrastructure/monitoring/jaeger/sampling-strategies.json`](infrastructure/monitoring/jaeger/sampling-strategies.json).

SLO definitions: [`docs/sre/slo/slo.yaml`](docs/sre/slo/slo.yaml)

---

## Agentic Spec-Driven Delivery Workflow

> A modern Agentic SDLC operating model that **replaces Gitflow-style release governance** while **preserving Agile principles** (fast feedback, collaboration, iterative delivery, continuous learning). **Agents draft, analyze, test, explain, recommend; humans approve, own, operate.**
>
> **Canonical reference:** [`docs/sdlc/agentic-spec-driven-delivery.md`](docs/sdlc/agentic-spec-driven-delivery.md) (ADR-0052, ADR-0058)

Features travel through a risk-based lifecycle from idea to post-deploy learning. AI agents participate as first-class contributors at each phase — with human review required at every phase boundary.

```
Phase  0: Intake          → Problem statement, value hypothesis, risk class, owner
Phase  1: Conception      → GitHub Issue (feature_request template)
Phase  2: Discovery       → Agent drafts discovery.md + nfr.md → Spec-as-PR review
Phase  3: Grooming        → DoR checklist; Issue reaches status: ready
Phase  4: Specification   → Agent drafts feature-spec.md → Spec-as-PR review
Phase  5: Architecture    → ADR filed if new architectural decision required
Phase  6: Development     → Branch + implementation against approved spec
Phase  7: Code Review     → PR + DoD checklist + CI gates
Phase  8: Testing         → Unit ≥ 80%, integration, security, abuse cases
Phase  9: DevSecOps       → SAST, SCA, Trivy, SBOM, DAST in staging
Phase 10: AI Safety       → Injection/leakage tests, tool-permission review (AI/agent features)
Phase 11: Observability   → OTel spans, Prometheus metrics, PRR sign-off
Phase 12: Release RC      → DoR-Release checklist; rc-approved label
Phase 13: Production      → Canary 5% → 25% → 100%; GitHub Release tag
Phase 14: Post-Deploy     → DORA metrics, sprint + release retrospectives
```

> Risk-based: low-risk changes take a short path; only high-impact / AI / security / infra changes pass every gate. See the canonical reference for the full risk-based flow.

| Process Document                 | Path                                                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| Canonical delivery model         | [`docs/sdlc/agentic-spec-driven-delivery.md`](docs/sdlc/agentic-spec-driven-delivery.md) |
| Phase lifecycle (15-phase, 0–14) | [`docs/process/WORKFLOW.md`](docs/process/WORKFLOW.md)                                   |
| HITL two-tier governance         | [`docs/process/HITL-GOVERNANCE.md`](docs/process/HITL-GOVERNANCE.md)                     |
| RACI matrix                      | [`docs/process/RACI.md`](docs/process/RACI.md)                                           |
| Definition of Ready              | [`docs/process/DEFINITION_OF_READY.md`](docs/process/DEFINITION_OF_READY.md)             |
| Definition of Done               | [`docs/process/DEFINITION_OF_DONE.md`](docs/process/DEFINITION_OF_DONE.md)               |
| Definition of Release            | [`docs/process/DEFINITION_OF_RELEASE.md`](docs/process/DEFINITION_OF_RELEASE.md)         |
| Retrospective guide              | [`docs/process/RETROSPECTIVE-GUIDE.md`](docs/process/RETROSPECTIVE-GUIDE.md)             |
| Progressive adoption (Tier 0–4)  | [`CUSTOMISING.md §8`](CUSTOMISING.md)                                                    |

**HITL Governance:** Pre-code artefacts (discovery.md, nfr.md, feature-spec.md) use **Spec-as-PR** review — not the runtime HITL gateway. The gateway is reserved for agent actions with real-world effects. See [`docs/process/HITL-GOVERNANCE.md`](docs/process/HITL-GOVERNANCE.md).

### Writing a spec → driving it with `/deliver`

Every feature starts as a spec (no code without a spec — CLAUDE.md §2). Use the canonical template:

1. **Copy the template:** [`specs/SPEC-TEMPLATE.md`](specs/SPEC-TEMPLATE.md) → `specs/<domain>/SPEC-<DOMAIN>-<NNN>-<slug>.md`. Its machine-readable metadata header and 16 sections **map 1:1 onto the 15 phases**, and a built-in _section → phase_ table shows which section feeds which gate (e.g. §8 Interface Contracts → Phase 4/6; §11 Governance/Privacy → Phase 9; §12 Acceptance Criteria → Phase 8 + becomes the dry-run evidence). See [`skills/sdlc/spec-lifecycle.md`](skills/sdlc/spec-lifecycle.md).
2. **Fill every section** (write `N/A — <reason>` where one genuinely doesn't apply), get it to `status: approved` via Spec-as-PR review.
3. **Drive the whole lifecycle:** `/deliver [dry-run|code] [tier] [language] specs/<domain>/<your-spec>.md` drives the spec through all 15 phases via the `phase-executor` subagent, and emits `reports/<slug>/FINAL-REPORT.md` with requirement-traceability, per-phase timing, gate verdicts, and the open-HITL list. The three optional axes default to **`dry-run` · `GOVERNED` · `PYTHON`** and are **classified by value**, so order and omission are tolerated (e.g. `/deliver code STANDARD java specs/…` ≡ `/deliver java code standard specs/…`):
   - **`mode`** ∈ {`dry-run`, `code`} — **default `dry-run`**.
     - **`dry-run`** — a **governed simulation** with no real side-effects; artefacts are drafted into `reports/<slug>/` and each gate is auto-approved-and-logged (a CLAUDE.md §14 escalation still STOPs the run, in both modes).
     - **`code`** — **real implementation** into the working tree (code, tests, ADRs, docs — local and uncommitted), running the real validation suite. It still **STOPS at every human gate** and never autonomously pushes, merges, releases, deploys, or changes autonomy flags (CLAUDE.md §3/§14).
   - **`tier`** ∈ {`TRIVIAL`, `STANDARD`, `GOVERNED`, `REGULATED`} — the **scope axis** (ADR-0064), **default `GOVERNED`** (conservative — omission never under-governs). It right-sizes which **process** phases run; **control phases (Testing, Security & DevSecOps, AI Safety, Code Review, Discovery PII classification, Production CAB, and the no-code-without-a-spec invariant) run in _every_ tier and are never waived**. A built-in **auto-escalation safety valve** promotes the tier mid-run (re-entering skipped phases, emitting a `TIER_ESCALATION` line) if a run exceeds its declared scope — a file/ADR/module ceiling, a coverage drop, a new dependency, an unanticipated control trigger, a >5-step task expansion, or a guardrail touch. Authoritative mapping: [`docs/process/gates/phase-gates.yaml`](docs/process/gates/phase-gates.yaml) (`tiers:`, each phase's `applicability:`, `escalation_triggers:`).
   - **`language`** ∈ {`PYTHON`, `JAVA`, `GO`, `NODE`, `TYPESCRIPT`, `IAC`, …} — **default `PYTHON`**. The stack to build in: `PYTHON` (`src/`), `JAVA`/`GO` (`services/<name>/`), `NODE`/`TYPESCRIPT` (`frontend/<app>/`), `IAC` (Terraform/Ansible → `infrastructure/`), or another stack. It selects the code location + validation targets; all gates and guardrails are language-agnostic.

   The skill never invents a spec. **Full guide:** [`docs/quickstart/delivering-a-spec.md`](docs/quickstart/delivering-a-spec.md) · skill source: [`.claude/skills/deliver/SKILL.md`](.claude/skills/deliver/SKILL.md).

> A well-filled `§12 Acceptance Criteria` is what gives `/deliver` real material to validate — each criterion becomes a row in the FINAL-REPORT traceability table.

> **🚀 See it end to end:** the **[worked walkthrough](docs/walkthrough.md)** narrates one real feature — the Log-Based Golden Signals service (SPEC-LGS-001) — through every phase (discovery → spec → ADR → code → eval → canary → SLO), with a link to each genuine artefact it produced. This is the canonical worked example.

---

## AI Governance

Every agent action with a real-world effect **must** route through the HITL gateway:

```python
from src.agents.hitl_gateway import HITLGateway, HITLRequest

await hitl_gateway.submit(HITLRequest(
    action="send-email",
    payload=safe_payload,   # PII-masked
    risk_score=0.85,        # above threshold → human approval required
))
```

| Control                  | Where                                      | Default                                             |
| ------------------------ | ------------------------------------------ | --------------------------------------------------- |
| HITL (Human in the Loop) | `src/agents/hitl_gateway.py`               | **on** — all high-risk actions require approval     |
| HOTL (Human on the Loop) | `autonomous-mode` feature flag             | **off** — must be enabled explicitly per ADR-0015   |
| HITL persistence         | `src/agents/hitl_store.py`                 | Redis-backed in production, in-memory for local dev |
| PII masking              | `src/guardrails/pii_filter.py`             | Always on — blocks if disabled                      |
| Prompt injection guard   | `src/guardrails/prompt_injection_guard.py` | Always on                                           |
| Audit log                | `src/guardrails/audit_logger.py`           | Immutable — all agent actions logged                |
| Ethical AI principles    | `specs/ethics/ethical-ai-principles.md`    | 6 principles, EU AI Act Arts. 9–15, LGPD Art. 20    |

Full AI governance: [`docs/ai-governance/`](docs/ai-governance/)

---

## Secure by Design — Agentic AI Compliance (v2.4.0)

This template implements a five-wave **Secure by Design** framework for agentic AI systems, aligned with the `secure-by-design-agentic-ai-compliance-v2.md` standard. Each wave is tracked as a GitHub Issue and delivered as a standalone, reviewable commit.

| Wave        | Issue | Pillar                                   | ADR      | Key Components                                                                          | Main Betterments                                                                                                                                                                                                                                                  |
| ----------- | ----- | ---------------------------------------- | -------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Wave 21** | #32   | Pillar 1 — Spec-Driven Guardrails        | ADR-0047 | `SpecContractEnforcer`, `ContextSeal`, `CodePreFlight`                                  | Runtime enforcement of spec boundaries — agents can only propose `allowed_action_types`; Planner→Generator context integrity sealed with SHA-256; AI-generated code blocked from forbidden imports (`subprocess`, `socket`, `eval`, `exec`) before sandbox entry  |
| **Wave 22** | #33   | Pillar 2 — Zero-Trust Tooling            | ADR-0048 | `ExecutionMode` enum, `ToolRegistry.is_sandbox_required()`, JWT operator auth           | Execution mode (`DIRECT \| SANDBOX`) declared at tool-registry time — sandbox routing becomes an architectural invariant, not a runtime guess; `execute-code` can never bypass the sandbox; HITL operator impersonation residual reduced Medium→Low               |
| **Wave 23** | #34   | Pillar 3 — Runtime Behavioral Monitoring | ADR-0049 | `BehavioralMonitor`, `RuntimePolicyGateway`, `policies.yaml`                            | Per-task-type frequency baseline detects action drift automatically (OTel span + Prometheus counter); declarative YAML policy engine enforces ALLOW / REQUIRE_HITL / BLOCK rules with hot-reload and PII-level awareness                                          |
| **Wave 24** | #35   | Pillar 4 — Continuous Verification       | ADR-0050 | `tests/abuse_cases/` (34 tests), `ActionSchemaValidator`, action schemas                | Structured abuse-case library (jailbreak, goal hijacking, context overflow, multi-agent trust, spec violations) runs on every PR with zero API cost; action payload schema validation blocks malformed or oversized payloads before HITL queuing                  |
| **Wave 25** | #36   | MLSecOps — Cross-Cutting                 | ADR-0051 | `tests/model_contract/` (11 tests), `ci-model-contract.yml`, `dependency-manifest.yaml` | Versioned behavioral contracts per model (`behavioral_contract_version`, `last_contract_tested`); real-LLM tests verify refusal behavior, spec adherence, and PII non-leakage; path-triggered CI fires only on model-version PRs — zero extra cost on normal runs |

### Cumulative Security Posture after All Waves

| Gap (pre-Wave 21)                                          | Closed by | Mechanism                                                                            |
| ---------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------ |
| Agent could propose any action regardless of spec          | Wave 21   | `SpecContractEnforcer.validate_action()` raises `SpecViolationError`                 |
| Planner output could be silently tampered between stages   | Wave 21   | `ContextSeal.verify()` raises `ContextTamperingError` on hash mismatch               |
| AI-generated code entered the sandbox unchecked            | Wave 21   | `CodePreFlight` AST gate rejects forbidden imports/calls                             |
| Tool→sandbox routing was implicit convention, not enforced | Wave 22   | `ExecutionMode.SANDBOX` declared in registry; `is_sandbox_required()` enforced       |
| HITL operator identity unverified in threat model          | Wave 22   | JWT operator auth already in place (REM-001 ✅); residual downgraded                 |
| No behavioral baseline — rogue action types undetected     | Wave 23   | `BehavioralMonitor` frequency baseline + drift counter                               |
| Policy enforcement was ad-hoc code, not declarative        | Wave 23   | `RuntimePolicyGateway` YAML policy engine with hot-reload                            |
| No structured adversarial test coverage on every PR        | Wave 24   | 34 mock-LLM abuse cases, `@pytest.mark.abuse_case`, added to `ci.yml`                |
| HITL received arbitrary-schema payloads unchecked          | Wave 24   | `ActionSchemaValidator` schema gate before `HITLGateway.submit_for_approval()`       |
| Model upgrades had no behavioral regression gate           | Wave 25   | `tests/model_contract/` + `ci-model-contract.yml` (path-triggered)                   |
| No versioned record of what behavior each model promises   | Wave 25   | `behavioral_contract_version` + `last_contract_tested` in `dependency-manifest.yaml` |

> **All five waves are committed to `main` and covered by ADR-0047–ADR-0051.** See [`docs/adr/README.md`](docs/adr/README.md) for the full index.

---

## Agentic SDLC E2E Workflow — Wave Summary (v2.6.0)

Four waves implementing the **13-phase Agentic SDLC E2E Workflow** (ADR-0052). Each wave is tracked as a GitHub Issue and delivered as a standalone, reviewable commit on `main`.

| Wave        | Issue | Theme                                                   | ADR                | Key Deliverables                                                                                                                                                                                                   | Main Betterments                                                                                                                                                                                                                                                                                                                 |
| ----------- | ----- | ------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Wave 26** | #38   | Foundation Templates + Process Directory                | ADR-0052           | `docs/process/WORKFLOW.md`, `DEFINITION_OF_READY.md`, `DEFINITION_OF_DONE.md`, `DEFINITION_OF_RELEASE.md`, `FEATURE_SPEC_TEMPLATE.md`, spike + RFC templates, `docs/product/README.md`, `specs/features/README.md` | 13-phase lifecycle documented end-to-end; global DoR/DoD/DoR-Release checklists give every team a single source of truth for phase entry/exit; 10-section feature spec template bounds agent implementation with Gherkin ACs, agent config, and security gates                                                                   |
| **Wave 27** | #39   | Governance Documents                                    | ADR-0052           | `docs/process/RACI.md`, `HITL-GOVERNANCE.md`, `SPRINT-TRACKING.md`, `RETROSPECTIVE-GUIDE.md`, `CONTRIBUTING.md` v2.5.0, `CUSTOMISING.md` Tier 0–4 guide                                                            | Two-tier HITL governance clarifies Spec-as-PR (pre-code artefacts) vs. runtime gateway (real-world actions) — no more ambiguity; 5-tier RACI eliminates ownership gaps at every DoD enforcement layer; dual retrospective cadence (sprint + release) aligns to ISO 27001 A.5.36 and EU AI Act Art. 72                            |
| **Wave 28** | #40   | Issue Lifecycle Automation + LLM Budget Circuit Breaker | ADR-0051, ADR-0052 | `issue-lifecycle.yml`, `llm-budget-tracker.yml`, `scripts/check_llm_budget.py`, updated `ci-model-contract.yml` (3-job budget-gated), `project-board-definition.json`                                              | Issue status labels transition automatically on PR events — zero manual label management; non-blocking LLM CI budget circuit breaker prevents unexpected spend spikes from blocking PRs while still surfacing cost alerts as PR comments; 5-view GitHub Projects board covers the full sprint lifecycle without external tooling |
| **Wave 29** | #41   | Harness Spec Lint Gate + ADR-0052 + Wire-up             | ADR-0052           | `harness/doc-check.yml` spec lint gate, `ADR-0052`, `CLAUDE.md` Pre-0f bootstrap step, `CLAUDE_SESSION_INIT.md` process quick reference, `README.md` SDLC section                                                  | CI now enforces spec-driven development automatically: FEAT-{id} spec file must exist, all ADR references must resolve on disk, and agent PRs must declare `allowed_action_types` — unblockable via convention; CLAUDE.md and SESSION_INIT updated so agents bootstrap Phase 1–2 correctly from the first session                |

### Process Gaps Closed by Waves 26–29

| Gap (pre-Wave 26)                                            | Closed by | Mechanism                                                                                   |
| ------------------------------------------------------------ | --------- | ------------------------------------------------------------------------------------------- |
| No defined phase lifecycle — every team improvised           | Wave 26   | `docs/process/WORKFLOW.md` 13-phase reference; quality gate at each phase boundary          |
| DoR/DoD existed only informally (PR checklist)               | Wave 26   | `DEFINITION_OF_READY.md` + `DEFINITION_OF_DONE.md` — global, versioned, CI-enforced         |
| No ownership clarity for DoD governance                      | Wave 27   | `RACI.md` 5-tier matrix; enforcement escalation path documented                             |
| Pre-code artefacts (discovery.md, nfr.md) had no HITL policy | Wave 27   | `HITL-GOVERNANCE.md` two-tier model — Spec-as-PR for artefacts, runtime gateway for actions |
| Issue status tracking was manual                             | Wave 28   | `issue-lifecycle.yml` auto-transitions on PR open/merge                                     |
| Model contract tests could exhaust LLM budget and block PRs  | Wave 28   | Non-blocking budget circuit breaker; skip + PR comment when cap reached                     |
| No sprint board — teams chose their own tools                | Wave 28   | `project-board-definition.json` 5-view GitHub Projects board (zero external SaaS)           |
| Spec-Driven Development enforced only by convention          | Wave 29   | `harness/doc-check.yml` `feature-spec-lint` gate — blocking CI check                        |
| Agent sessions had no Phase 1–2 guidance                     | Wave 29   | `CLAUDE.md` Pre-0f bootstrap step + `CLAUDE_SESSION_INIT.md` process quick reference        |
| No cross-cutting ADR for the full lifecycle                  | Wave 29   | `ADR-0052` — 13-phase workflow + Q1–Q6 decisions permanently recorded                       |

> **All four waves are committed to `main` and governed by ADR-0052.** See [`docs/process/WORKFLOW.md`](docs/process/WORKFLOW.md) for the full lifecycle reference.

---

## Feature Flags

Flags use the [OpenFeature](https://openfeature.dev/) SDK (CNCF standard) backed by [flagd](https://flagd.dev/). No external SaaS dependency — flags are YAML files mounted via ConfigMap.

| Flag              | Default | Effect                                                     |
| ----------------- | ------- | ---------------------------------------------------------- |
| `autonomous-mode` | `off`   | When `on`, enables HOTL — agents act without HITL approval |

To change a flag locally: edit `infrastructure/feature-flags/flags/autonomous-mode.yaml`, then restart flagd (`docker compose restart flagd`). Governance approval required before enabling `autonomous-mode` in production (ADR-0015).

To verify the current state: `cat infrastructure/feature-flags/flags/autonomous-mode.yaml`

---

## CI / CD

Path-filtered CI workflows — each language's pipeline only runs when its code changes:

| Workflow          | Triggered by                         | Key gates                                                                                                                              |
| ----------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `ci.yml`          | all pushes                           | Governance checks (incl. **control-binding gate**, ADR-0061) · lint · unit ≥ 80% · integration · security · contract drift · env drift |
| `ci-java.yml`     | `services/**/*.java`, `**/pom.xml`   | Checkstyle · SpotBugs · OWASP dep-check · JaCoCo ≥ 80% · Testcontainers                                                                |
| `ci-go.yml`       | `services/**/*.go`, `**/go.mod`      | `go mod tidy` · golangci-lint · race detector · proto drift · 80% coverage                                                             |
| `ci-frontend.yml` | `frontend/**`, `docs/api/openapi/**` | ESLint · TS type-check · API client drift · Jest ≥ 80% · Playwright                                                                    |

**Control-binding gate (ADR-0061).** The `Governance Checks` job runs
`scripts/governance/check_control_bindings.py`: if a PR touches a controlled surface
(per `.github/control-triggers.yml`) but its `## Skills — load before executing` block
omits the matching control, the gate reports a violation. It also enforces the 2-skill
budget and flags the 3-domain atomicity smell, and respects conditional controls via
`docs/governance/applicability-matrix.yml`. It enforces _declaration discipline_, not
compliance correctness. It ships in **report mode** for the initial rollout cycle
(RFC-0004 §5) — remove `continue-on-error` from the CI step to make it blocking. Run it
locally with `make check-control-bindings`.

CD workflows:

| Workflow            | Trigger         | Strategy                                                                      |
| ------------------- | --------------- | ----------------------------------------------------------------------------- |
| `cd-staging.yml`    | Merge to main   | Build + push image · Helm deploy · smoke tests                                |
| `cd-production.yml` | Manual dispatch | Error budget check → 5% canary → 25% canary → 100% · auto-rollback on failure |

---

## Architecture Decisions

All 51 ADRs are recorded in [`docs/adr/`](docs/adr/README.md). Key decisions:

| ADR                                                                | Decision                                               |
| ------------------------------------------------------------------ | ------------------------------------------------------ |
| [ADR-0001](docs/adr/ADR-0001-monorepo-structure-and-governance.md) | Monorepo structure and governance                      |
| [ADR-0002](docs/adr/ADR-0002-technology-stack-selection.md)        | Technology stack selection (Python · Java · Go · Node) |
| [ADR-0003](docs/adr/ADR-0003-async-api-strategy.md)                | Async-first — Kafka vs REST vs gRPC                    |
| [ADR-0006](docs/adr/ADR-0006-deployment-strategy.md)               | Canary deployment strategy                             |
| [ADR-0010](docs/adr/ADR-0010-agent-framework-selection.md)         | Agent framework selection                              |
| [ADR-0011](docs/adr/ADR-0011-hitl-hotl-model.md)                   | Human oversight model (HITL / HOTL)                    |
| [ADR-0012](docs/adr/ADR-0012-pii-masking-strategy.md)              | PII masking before LLM ingestion and logging           |
| [ADR-0014](docs/adr/ADR-0014-multi-agent-harness-strategy.md)      | Multi-agent harness (Planner → Generator → Evaluator)  |
| [ADR-0015](docs/adr/ADR-0015-feature-flag-strategy.md)             | Feature flags via OpenFeature + flagd                  |
| [ADR-0018](docs/adr/ADR-0018-db-encryption-at-rest.md)             | Database encryption at rest (AES-256-GCM)              |
| [ADR-0019](docs/adr/ADR-0019-redis-tls-value-encryption.md)        | Redis TLS and value encryption                         |
| [ADR-0020](docs/adr/ADR-0020-finops-cost-allocation.md)            | LLM cost allocation and budget enforcement             |
| [ADR-0021](docs/adr/ADR-0021-agent-communication-protocol.md)      | Agent communication protocol (Protobuf)                |
| [ADR-0026](docs/adr/ADR-0026-sox-audit-log-immutability.md)        | SOX audit log immutability and retention               |
| [ADR-0027](docs/adr/ADR-0027-iso27001-change-management.md)        | ISO 27001 three-tier change management                 |
| [ADR-0028](docs/adr/ADR-0028-dora-metrics.md)                      | DORA metrics — Elite targets and enforcement           |
| [ADR-0029](docs/adr/ADR-0029-devsecops-pipeline-security.md)       | DevSecOps pipeline security (SAST, SCA, IaC, SBOM)     |

---

## Privacy

This template processes personal data subject to **LGPD** (Brazil) and **GDPR** (EU):

- PII is classified L1–L4 and masked before LLM calls, logging, and event publishing
- DPIA and RIPD documents are pre-filled in `docs/privacy/`
- Data retention is automated per policy in `src/jobs/`
- Data subject rights (access, erasure, portability) handled per `skills/privacy/data-subject-rights.md`

Privacy docs: [`docs/privacy/`](docs/privacy/)

---

## Security

STRIDE threat model covering all six attack categories is in [`specs/security/threat-model.md`](specs/security/threat-model.md).

Key controls: JWT auth, TLS everywhere, AES-256-GCM at rest, PII masking, prompt injection guard, sandbox execution isolation, immutable audit log, SAST (Bandit + SpotBugs + gosec), secret scanning (detect-secrets), SBOM (Syft + Cosign attestation).

To report a vulnerability: [`SECURITY.md`](SECURITY.md).

---

## For AI coding agents

Using Claude Code, Copilot, or Cursor in this repo? Read [`AGENTS.md`](AGENTS.md) — the
contract that keeps agents from weakening governance, leaking secrets, or bypassing CI
gates (files not to edit casually, required workflow, hard prohibitions, validation
commands). Claude Code users should also read [`CLAUDE.md`](CLAUDE.md).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the SDD cycle, branch naming, commit conventions, and PR process.

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community standards.

---

## Troubleshooting

First-run problems? See [`docs/troubleshooting.md`](docs/troubleshooting.md) (the 15 most
common failures) — or run `make doctor`, which detects most of them automatically.

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).
