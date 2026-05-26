# Enterprise AI Monorepo Template

> Production-ready monorepo template for AI-powered systems.
> **Version:** 1.1.0 | **Status:** Active | **License:** Proprietary

[![CI](https://github.com/valdomirosouza/template-monorepo/actions/workflows/ci.yml/badge.svg)](https://github.com/valdomirosouza/template-monorepo/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/valdomirosouza/template-monorepo)](https://github.com/valdomirosouza/template-monorepo/releases/latest)

---

## Use this template

Click **"Use this template"** on the GitHub repository page, or run:

```bash
gh repo create my-project --template valdomirosouza/template-monorepo --clone
cd my-project
```

Then follow the **5-step setup** below to go from blank repo to running system.

---

## What you get

A production-ready scaffold for teams building AI-powered systems with human oversight. Everything is wired together from day one:

| Layer              | What's included                                                         |
| ------------------ | ----------------------------------------------------------------------- |
| **Languages**      | Python 3.12 · Java 21 · Go 1.23 · Node 20 / Next.js 14                  |
| **AI**             | Anthropic Claude · HITL/HOTL gateway · multi-agent harness · guardrails |
| **Infrastructure** | PostgreSQL · Redis · Kafka (KRaft) · Schema Registry · flagd            |
| **Observability**  | OpenTelemetry · Prometheus · Grafana (Golden Signals + CUJ) · Jaeger    |
| **Governance**     | 15 ADRs · SDD cycle · privacy-by-design (LGPD + GDPR) · PRR checklist   |
| **CI/CD**          | GitHub Actions for Python · Java · Go · Frontend — all path-filtered    |
| **Dev experience** | Devcontainer · `docker compose up -d` · per-language `make` targets     |

---

## 5-step setup

### Step 1 — Start the infrastructure

```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, SECRET_KEY
# Everything else has working local defaults

make infra-up
# Starts: PostgreSQL, Redis, Kafka, Schema Registry,
#         OTel Collector, Jaeger, Prometheus, Grafana, flagd
```

### Step 2 — Run database migrations

```bash
make setup   # installs Python deps + runs Alembic migrations
```

### Step 3 — Verify baseline is green

```bash
make test-python    # unit + integration + security
make lint-python    # ruff + mypy + secret scan
```

### Step 4 — Open your language quickstart

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

### Step 5 — Customise for your project

| File                 | What to change                                              |
| -------------------- | ----------------------------------------------------------- |
| `services.yaml`      | Rename services, add your own, update ports and topic names |
| `.env.example`       | Add project-specific environment variables                  |
| `docs/adr/`          | Add ADRs for your own architectural decisions               |
| `specs/`             | Write specs for features before implementing                |
| `CLAUDE.md`          | Adjust AI behavioral contract for your team                 |
| `.github/CODEOWNERS` | Set team ownership                                          |

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

# Contracts
make openapi-ui        # Swagger UI at http://localhost:8082
make asyncapi-ui       # AsyncAPI Studio at http://localhost:8083
make gen-api-client-ts # regenerate TypeScript client from OpenAPI
make gen-proto-go      # regenerate Go gRPC stubs from proto

# Scaffold a new service
make new-service NAME=my-service LANG=python   # or java / go
```

---

## Repository Structure

```
.
├── CLAUDE.md                    ← AI behavioral contract (v2.0.0)
├── services.yaml                ← Service catalog (all languages, ports, topics)
├── docker-compose.yml           ← Full dev infrastructure stack
├── docker-compose.test.yml      ← Lightweight test stack (offset ports)
├── .devcontainer/               ← Multi-language devcontainer (Python+Java+Go+Node)
│
├── docs/
│   ├── quickstart/              ← Role-specific onboarding guides (5 languages)
│   ├── adr/                     ← Architecture Decision Records (ADR-0001–0015)
│   ├── api/                     ← OpenAPI · AsyncAPI · gRPC proto contracts
│   ├── privacy/                 ← PII inventory, DPIA/RIPD, data retention
│   ├── sre/                     ← SLOs, error budget policy, PRR, CUJ
│   ├── runbooks/                ← RB-003 HITL recovery + rollback + DR
│   └── ai-governance/           ← Model card, EU AI Act, NIST AI RMF
│
├── specs/                       ← Spec-Driven Development specs (write before code)
│   ├── system/                  ← Vision, architecture, async event flow
│   ├── ai/                      ← Agent design, HITL/HOTL, guardrails, harness
│   └── privacy/                 ← PII, retention, DPIA/RIPD
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
├── services/                    ← Java / Go service directories (add yours here)
├── frontend/                    ← Next.js applications (add yours here)
│
├── infrastructure/
│   ├── k8s/                     ← Deployment · Service · HPA · PDB manifests
│   ├── feature-flags/           ← flagd + autonomous-mode.yaml (OpenFeature)
│   └── monitoring/
│       ├── prometheus/          ← prometheus.yml scrape config + alert rules
│       └── grafana/             ← Dashboards (Golden Signals · SRE · CUJ-001)
│                                   + datasource & dashboard provisioning
│
├── tests/                       ← Unit · Integration · Security · Chaos
├── .github/workflows/           ← CI: Python · Java · Go · Frontend (path-filtered)
└── skills/                      ← Claude Code enterprise skills catalog
```

Full annotated tree: [`docs/repo-structure.md`](docs/repo-structure.md)

---

## API Contracts

| Type   | Spec                                                                           | Description                            |
| ------ | ------------------------------------------------------------------------------ | -------------------------------------- |
| REST   | [`docs/api/openapi/v1/openapi.yaml`](docs/api/openapi/v1/openapi.yaml)         | Synchronous REST API (OpenAPI 3.1)     |
| Events | [`docs/api/asyncapi/v1/asyncapi.yaml`](docs/api/asyncapi/v1/asyncapi.yaml)     | Kafka event contracts (AsyncAPI 2.6)   |
| gRPC   | [`docs/api/grpc/proto/ai_service.proto`](docs/api/grpc/proto/ai_service.proto) | Inter-service calls (Protocol Buffers) |

> **Rule:** Never write stubs by hand. Generate from the contracts — see [`docs/quickstart/contract-driven-dev.md`](docs/quickstart/contract-driven-dev.md).

---

## Observability

| Signal                   | Stack                            | Location                                      |
| ------------------------ | -------------------------------- | --------------------------------------------- |
| Metrics (Golden Signals) | Prometheus + Grafana             | http://localhost:3001 (admin/admin)           |
| Traces                   | OpenTelemetry + Jaeger           | http://localhost:16686                        |
| Logs                     | Structured JSON + OTel Collector | —                                             |
| SLO / Error Budget       | Prometheus + Grafana             | `sre-overview.json` dashboard                 |
| CUJ-001 dashboard        | Prometheus + Grafana             | `cuj-dashboards/CUJ-001-*.json`               |
| Alerting                 | PrometheusRule                   | `infrastructure/monitoring/prometheus/rules/` |

All dashboards and datasources are **provisioned automatically** — no manual import needed after `make infra-up`.

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

Full AI governance: [`docs/ai-governance/`](docs/ai-governance/)

---

## Feature Flags

Flags use the [OpenFeature](https://openfeature.dev/) SDK (CNCF standard) backed by [flagd](https://flagd.dev/). No external SaaS dependency — flags are YAML files mounted via ConfigMap.

| Flag              | Default | Effect                                                     |
| ----------------- | ------- | ---------------------------------------------------------- |
| `autonomous-mode` | `off`   | When `on`, enables HOTL — agents act without HITL approval |

To change a flag locally: edit `infrastructure/feature-flags/flags/autonomous-mode.yaml`, then restart flagd (`docker compose restart flagd`). Governance approval required before enabling `autonomous-mode` in production (ADR-0015).

---

## CI / CD

Four path-filtered workflows — each language's CI only runs when its code changes:

| Workflow          | Triggered by                         | Key gates                                                           |
| ----------------- | ------------------------------------ | ------------------------------------------------------------------- |
| `ci.yml`          | all pushes                           | Python lint + unit ≥ 80% + integration + security + contract drift  |
| `ci-java.yml`     | `services/**/*.java`, `**/pom.xml`   | Checkstyle · SpotBugs · JaCoCo ≥ 80% · Testcontainers               |
| `ci-go.yml`       | `services/**/*.go`, `**/go.mod`      | golangci-lint · race detector · proto drift · 80% coverage          |
| `ci-frontend.yml` | `frontend/**`, `docs/api/openapi/**` | ESLint · TS type-check · API client drift · Jest ≥ 80% · Playwright |

The `contract-drift` job in `ci.yml` verifies that OpenAPI/AsyncAPI specs parse, proto files compile, and all `services.yaml` schema references exist on disk.

---

## Architecture Decisions

All significant architectural decisions are recorded as ADRs in [`docs/adr/`](docs/adr/README.md).

| ADR                                                                | Decision                                               |
| ------------------------------------------------------------------ | ------------------------------------------------------ |
| [ADR-0001](docs/adr/ADR-0001-monorepo-structure-and-governance.md) | Monorepo structure and governance                      |
| [ADR-0002](docs/adr/ADR-0002-technology-stack-selection.md)        | Technology stack selection (Python · Java · Go · Node) |
| [ADR-0003](docs/adr/ADR-0003-async-api-strategy.md)                | Async-first — Kafka vs REST vs gRPC                    |
| [ADR-0010](docs/adr/ADR-0010-agent-framework-selection.md)         | Agent framework selection                              |
| [ADR-0011](docs/adr/ADR-0011-hitl-hotl-model.md)                   | Human oversight model (HITL / HOTL)                    |
| [ADR-0012](docs/adr/ADR-0012-pii-masking-strategy.md)              | PII masking before LLM ingestion and logging           |
| [ADR-0014](docs/adr/ADR-0014-multi-agent-harness-strategy.md)      | Multi-agent harness (Planner → Generator → Evaluator)  |
| [ADR-0015](docs/adr/ADR-0015-feature-flag-strategy.md)             | Feature flags via OpenFeature + flagd                  |

---

## Privacy

This template processes personal data subject to **LGPD** (Brazil) and **GDPR** (EU):

- PII is classified L1–L4 and masked before LLM calls, logging, and event publishing
- DPIA and RIPD templates are pre-filled in `docs/privacy/`
- Data retention is automated per policy in `src/jobs/`

Privacy docs: [`docs/privacy/`](docs/privacy/)

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the SDD cycle, branch naming, commit conventions, and PR process.

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community standards.

---

## Security

To report a vulnerability, see [`SECURITY.md`](SECURITY.md).

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).
