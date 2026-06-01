# Enterprise Monorepo Template

> Production-ready monorepo template for enterprise software systems. AI/agent capabilities are optional opt-in extensions.
> **Version:** 1.26.19 | **Status:** Active | **License:** MIT

[![CI](https://github.com/valdomirosouza/Repository-Template/actions/workflows/ci.yml/badge.svg)](https://github.com/valdomirosouza/Repository-Template/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/valdomirosouza/Repository-Template)](https://github.com/valdomirosouza/Repository-Template/releases/latest)

---

## Quick Start: Clone → Initial Setup → Code

### 1. Clone

Click **"Use this template"** on the GitHub repository page, or run:

```bash
gh repo create my-project --template valdomirosouza/Repository-Template --clone
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
# ANTHROPIC_API_KEY is only needed if you use the AI Agents extension.

# Install Python deps, start all infrastructure containers, run DB migrations
make setup

# Confirm everything is alive
curl http://localhost:8000/health   # → {"status": "ok"}
curl http://localhost:8000/ready    # → {"status": "ready"}
```

> If `/ready` returns `503`, run `docker compose ps` — PostgreSQL or Redis may still be initialising.

**What `make setup` starts:**

| Container       | Port(s)     | Role                                               |
| --------------- | ----------- | -------------------------------------------------- |
| PostgreSQL      | 5432        | Audit log, pgvector agent memory                   |
| Redis           | 6379        | HITL store, request store, session cache           |
| Kafka (KRaft)   | 9092        | Async event broker                                 |
| Schema Registry | 8081        | Avro schema validation                             |
| OTel Collector  | 4317 (gRPC) | Traces, metrics, logs aggregator                   |
| Prometheus      | 9090        | Metrics scrape + alerting                          |
| Grafana         | 3001        | Dashboards — http://localhost:3001 (admin / admin) |
| Jaeger          | 16686       | Distributed trace UI                               |
| flagd           | 8013        | OpenFeature flag server                            |
| Alertmanager    | 9093        | Alert routing (PagerDuty / Slack integration)      |

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

| Layer                    | What's included                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| **Languages**            | Python 3.13 · Java 21 · Go 1.24 · Node 22 / Next.js 15                                          |
| **Service scaffolds**    | `services/domain-service/` (Spring Boot) · `services/event-worker/` (Go) · `frontend/frontend/` |
| **Infrastructure**       | PostgreSQL · Redis · Kafka (KRaft) · Schema Registry · flagd                                    |
| **IaC**                  | Helm chart for Kubernetes · Terraform modules for VPC, EKS, and ElastiCache Redis               |
| **Observability**        | OpenTelemetry · Prometheus · Grafana (Golden Signals + CUJ) · Jaeger (with sampling policy)     |
| **Alerting**             | Golden Signals rules + 14 agent-specific alert rules (HITL, feedback loop, MTTD/MTTR, LLM cost) |
| **Governance**           | 21 ADRs · SDD cycle · STRIDE threat model · privacy-by-design (LGPD + GDPR) · PRR checklist     |
| **Specs**                | System · AI/agents · Privacy · Security (STRIDE) · Ethics (EU AI Act) · SDLC lifecycle          |
| **CI/CD**                | GitHub Actions for Python · Java · Go · Frontend — all path-filtered · canary CD with SLO gates |
| **Testing**              | Unit · Integration · Security · Chaos · Contract tests (harness message schema invariants)      |
| **Dev experience**       | Devcontainer · `docker compose up -d` · per-language `make` targets · skills catalog            |
| **AI/Agents** _(opt-in)_ | Anthropic Claude · HITL/HOTL gateway · multi-agent harness · guardrails · ethical AI principles |

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

# Scaffold a new service
make new-service NAME=my-service LANG=python   # or java / go
```

---

## Repository Structure

```
.
├── CLAUDE.md                    ← AI behavioral contract (v2.1.1)
├── services.yaml                ← Service catalog (all languages, ports, topics)
├── docker-compose.yml           ← Full dev infrastructure stack
├── docker-compose.test.yml      ← Lightweight test stack (offset ports)
├── .devcontainer/               ← Multi-language devcontainer (Python+Java+Go+Node)
│
├── docs/
│   ├── quickstart/              ← Role-specific onboarding guides (5 languages)
│   ├── adr/                     ← Architecture Decision Records (ADR-0001–0030)
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
├── .github/workflows/           ← CI: Python · Java · Go · Frontend (path-filtered)
│                                   CD: staging (auto) · production (canary, manual)
└── skills/                      ← Claude Code enterprise skills catalog
    ├── sre/                     ← golden-signals · prr · cuj · incident-response · capacity-planning
    ├── privacy/                 ← pii · lgpd · gdpr · data-subject-rights
    ├── change-management/       ← rfc-process · deploy-rollback · cab-process
    ├── ai/                      ← guardrails · harness
    ├── observability/           ← otel-instrumentation
    ├── api/                     ← rest-api-design
    ├── devsecops/               ← secret-scanning
    ├── sdlc/                    ← spec-lifecycle
    └── token-efficiency/        ← rtk-setup · rtk-commands · rtk-context-hygiene
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

## Feature Flags

Flags use the [OpenFeature](https://openfeature.dev/) SDK (CNCF standard) backed by [flagd](https://flagd.dev/). No external SaaS dependency — flags are YAML files mounted via ConfigMap.

| Flag              | Default | Effect                                                     |
| ----------------- | ------- | ---------------------------------------------------------- |
| `autonomous-mode` | `off`   | When `on`, enables HOTL — agents act without HITL approval |

To change a flag locally: edit `infrastructure/feature-flags/flags/autonomous-mode.yaml`, then restart flagd (`docker compose restart flagd`). Governance approval required before enabling `autonomous-mode` in production (ADR-0015).

To verify the current state: `cat infrastructure/feature-flags/flags/autonomous-mode.yaml`

---

## CI / CD

Four path-filtered CI workflows — each language's pipeline only runs when its code changes:

| Workflow          | Triggered by                         | Key gates                                                                                   |
| ----------------- | ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `ci.yml`          | all pushes                           | Governance checks · lint · unit ≥ 80% · integration · security · contract drift · env drift |
| `ci-java.yml`     | `services/**/*.java`, `**/pom.xml`   | Checkstyle · SpotBugs · OWASP dep-check · JaCoCo ≥ 80% · Testcontainers                     |
| `ci-go.yml`       | `services/**/*.go`, `**/go.mod`      | `go mod tidy` · golangci-lint · race detector · proto drift · 80% coverage                  |
| `ci-frontend.yml` | `frontend/**`, `docs/api/openapi/**` | ESLint · TS type-check · API client drift · Jest ≥ 80% · Playwright                         |

CD workflows:

| Workflow            | Trigger         | Strategy                                                                      |
| ------------------- | --------------- | ----------------------------------------------------------------------------- |
| `cd-staging.yml`    | Merge to main   | Build + push image · Helm deploy · smoke tests                                |
| `cd-production.yml` | Manual dispatch | Error budget check → 5% canary → 25% canary → 100% · auto-rollback on failure |

---

## Architecture Decisions

All 30 ADRs are recorded in [`docs/adr/`](docs/adr/README.md). Key decisions:

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
| [ADR-0030](docs/adr/ADR-0030-rtk-token-efficiency.md)              | RTK token efficiency integration (developer tool)      |

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

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the SDD cycle, branch naming, commit conventions, and PR process.

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community standards.

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).
