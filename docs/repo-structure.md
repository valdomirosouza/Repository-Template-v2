# Repository Structure — Annotated Directory Tree

> Auto-generated reference. If the actual tree diverges from this document, update
> this file as part of the PR that changes the structure.

---

## Root

```
<project-name>/
├── CLAUDE.md              ← Behavioral contract for Claude Code (AI tooling)
├── README.md              ← Project entry point and quick-start guide
├── CHANGELOG.md           ← Keep-a-Changelog; updated on every release
├── SECURITY.md            ← Vulnerability disclosure policy
├── PRIVACY.md             ← Data processing notice (LGPD / GDPR)
├── CONTRIBUTING.md        ← SDD cycle, branch naming, PR process
├── CODE_OF_CONDUCT.md     ← Community standards (Contributor Covenant 2.1)
├── LICENSE                ← Software licence
├── version.txt            ← Canonical version (single source of truth)
├── .env.example           ← All required environment variables (no real values)
├── Makefile               ← make setup | test | lint | deploy-staging | rollback
├── .gitignore             ← Python + Node.js + secrets + IDE
├── Dockerfile             ← Multi-stage production container
├── docker-compose.yml     ← Full local dev stack
├── pyproject.toml         ← Python project config (uv / poetry)
└── requirements.txt       ← Pinned runtime dependencies
```

**Owner:** Tech Lead

---

## `docs/` — Documentation & Governance

```
docs/
├── adr/                   ← Architecture Decision Records (binding)
│   ├── README.md          ← ADR template + master index
│   └── ADR-NNNN-*.md      ← One file per decision
│
├── api/                   ← API specifications
│   ├── openapi/v1/        ← OpenAPI 3.1 REST spec
│   ├── asyncapi/v1/       ← AsyncAPI 2.6 event contracts
│   └── grpc/proto/        ← Protobuf definitions
│
├── runbooks/              ← Operational runbooks (blameless format)
├── postmortems/           ← Historical post-mortems
├── security/              ← Threat model, OWASP assessments, pentest reports
│
├── privacy/               ← Data privacy documentation (DPO-owned)
│   ├── dpia/              ← GDPR Art. 35 impact assessments
│   ├── ripd/              ← LGPD Art. 38 impact reports
│   ├── pii-inventory.md   ← PII fields catalogue + L1–L4 classification
│   ├── data-retention-policy.md
│   └── data-processing-register.md  ← RoPA (GDPR Art. 30)
│
├── ai-governance/         ← AI-specific governance (AI Governance Lead + DPO)
│   ├── model-card.md
│   ├── eu-ai-act-compliance.md
│   ├── nist-ai-rmf.md
│   └── autonomy-boundaries.md
│
├── sre/                   ← SRE artifacts (SRE Lead)
│   ├── slo/               ← SLO/SLI definitions + error budget policy
│   ├── prr/               ← Production Readiness Review template + checklist
│   └── cuj/               ← Critical User Journey definitions
│
├── change-management/     ← ITIL-aligned change process (Tech Lead + SRE Lead)
│   ├── README.md          ← Full 8-step process
│   ├── RFC-TEMPLATE.md
│   ├── CAB-PROCESS.md
│   └── rfc/               ← Archived RFCs
│
├── glossary.md            ← Canonical term definitions
└── repo-structure.md      ← This file
```

**Owner:** Tech Lead. Sub-sections owned as noted.

---

## `specs/` — Spec-Driven Development

```
specs/
├── README.md              ← Spec hierarchy + ownership table
├── system/                ← System-level specs (Product Owner + Tech Lead)
│   ├── vision.md
│   ├── architecture.md
│   └── async-event-flow.md
├── ai/                    ← AI agent specs (AI Lead + Security Lead)
│   ├── agent-design.md
│   ├── hitl-hotl.md
│   └── guardrails.md
└── privacy/               ← Privacy specs (DPO)
    ├── pii-inventory.md
    ├── data-retention.md
    └── dpia-ripd.md
```

**Rule:** No code is written without a referenced spec. Every PR must include a
`specs/*` path in the PR description.

---

## `src/` — Application Source Code

```
src/
├── agents/                ← AI agent components
│   ├── hitl_gateway.py    ← HITL approval gateway (Security + AI Governance dual-approval)
│   └── orchestrator/      ← Multi-agent coordinator and task router
│
├── api/                   ← API layer
│   ├── rest/              ← FastAPI synchronous REST
│   ├── async/             ← Kafka consumers and producers
│   └── grpc/              ← gRPC server and generated stubs
│
├── memory/                ← Vector store and document indexer (RAG)
│
├── guardrails/            ← Safety controls (Security Lead — changes need review)
│   ├── pii_filter.py      ← PII masking (L1–L4); runs at 3 interception points
│   ├── prompt_injection_guard.py ← Input validation (structural checks only)
│   ├── output_validator.py
│   ├── action_limits.py   ← Per-agent rate limits and scope limits
│   └── audit_logger.py    ← Immutable append-only audit log
│
├── observability/         ← Instrumentation (SRE Lead)
│   ├── otel_setup.py      ← OpenTelemetry SDK bootstrap
│   ├── metrics.py         ← Prometheus Golden Signals metrics
│   ├── logger.py          ← Structured JSON logger with PII masking
│   └── tracer.py          ← Distributed tracing helpers
│
└── shared/                ← Shared utilities (Tech Lead)
    ├── config.py          ← Pydantic Settings (all env vars)
    ├── models.py          ← Base domain models
    ├── exceptions.py
    └── constants.py
```

---

## `tests/` — Test Suite

```
tests/
├── README.md              ← Testing strategy + pyramid rationale
├── conftest.py            ← Global pytest fixtures
├── unit/                  ← Unit tests (coverage ≥ 80% required)
├── integration/           ← Integration tests (real services or test containers)
├── e2e/                   ← End-to-end full user flow tests
├── contract/              ← Consumer-driven contract tests (Pact)
├── performance/           ← Load tests (k6 + Locust)
├── security/              ← Defensive validation suite (guardrails + PII leakage)
├── chaos/                 ← Chaos experiments + game day runbooks
└── fixtures/              ← Synthetic, PII-free test data
```

---

## `infrastructure/` — Infrastructure as Code

```
infrastructure/
├── terraform/             ← IaC modules and environment configs
├── helm/                  ← Kubernetes deployment charts
├── monitoring/            ← Observability configuration
│   ├── prometheus/rules/  ← Alerting rules (Golden Signals + SLO burn rate)
│   ├── grafana/dashboards/← Dashboard JSON files
│   ├── jaeger/            ← Distributed tracing backend config
│   └── opentelemetry/     ← OTel Collector config
├── message-broker/        ← Kafka topic definitions + Avro schemas
├── feature-flags/         ← Feature flag configuration
└── scripts/deploy/        ← deploy.sh, rollback.sh, smoke-test.sh
```

**Owner:** DevOps Lead + SRE Lead

---

## `.github/` — CI/CD & Repository Configuration

```
.github/
├── workflows/             ← GitHub Actions pipelines
│   ├── ci.yml             ← Validate → Test → Security → Build → Staging Deploy
│   ├── cd-production.yml  ← Canary deploy + Golden Signals gate
│   ├── sbom.yml           ← SBOM generation + Cosign signing
│   └── ...
├── ISSUE_TEMPLATE/        ← Bug report, change request, security advisory
├── pull_request_template.md
└── CODEOWNERS             ← Code ownership by directory
```

---

## `harness/` — Quality Gate Definitions

```
harness/
├── code-check.yml         ← PR gate: lint + unit + SAST + secrets
├── staging-check.yml      ← Staging gate: integration + DAST + performance
├── release-check.yml      ← Release gate: SBOM + error budget + PRR
└── doc-check.yml          ← Doc gate: changelog + spec + ADR
```

---

## `skills/` — Claude Code Enterprise Skills

```
skills/
├── README.md              ← Skills catalog
├── sre/                   ← Golden Signals, PRR, CUJ skills
├── ai/                    ← Guardrails skill
├── privacy/               ← PII, LGPD, GDPR skills
└── change-management/     ← RFC process, deploy/rollback skills
```

Activated via the Skill Activation Table in `CLAUDE.md`.
