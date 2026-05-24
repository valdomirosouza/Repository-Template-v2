# <project-name>

> Enterprise AI-powered system — production-ready monorepo template
> **Version:** 0.1.0 | **Status:** Active

---

## Usando como Template — Scaffolding

Este repositório é um **template de monorepo**. Para gerar todos os arquivos de governança,
specs, CI/CD, código-fonte e documentação em um repositório novo, use a pasta `SETUP/`.

### Pré-requisitos

- [Claude Code](https://claude.ai/code) instalado e autenticado
- Python 3.12+, Docker & Docker Compose, `make`, `uv`

### Execução guiada (12 prompts)

```bash
# 1. Clone ou inicialize o repositório vazio
git init my-project && cd my-project

# 2. Coloque o MONOREPO-STRUCTURE-EN.md e a pasta SETUP/ na raiz
# 3. No Claude Code, execute cada prompt em ordem:
Read SETUP/001-prompt.md carefully and execute every instruction in it.
# Aguarde a conclusão, depois repita para 002, 003, ... até 012
```

| #   | Prompt          | Conteúdo                                   | Arquivos |
| --- | --------------- | ------------------------------------------ | -------- |
| 1   | `001-prompt.md` | Estrutura de diretórios + `.gitkeep`       | ~55 dirs |
| 2   | `002-prompt.md` | Arquivos raiz de governança                | 10       |
| 3   | `003-prompt.md` | ADRs + Glossário + Repo structure          | 8        |
| 4   | `004-prompt.md` | Privacy docs + AI Governance               | 9        |
| 5   | `005-prompt.md` | SRE + Change Management + Runbooks         | 11       |
| 6   | `006-prompt.md` | Specs (SDD)                                | 10       |
| 7   | `007-prompt.md` | CI/CD workflows + Harness                  | 14       |
| 8   | `008-prompt.md` | Infrastructure monitoring + Skills         | 17       |
| 9   | `009-prompt.md` | Source code: agents, observability, shared | 8        |
| 10  | `010-prompt.md` | Guardrails + Security tests ⚠️             | 7        |
| 11  | `011-prompt.md` | Postmortem template                        | 1        |
| 12  | `012-prompt.md` | Validação final (somente leitura)          | 0        |

> ⚠️ Prompt 010 contém arquivos de guardrails (detecção defensiva). Todos os inputs de teste
> usam tokens sintéticos (`SYNTHETIC_INJECT_ATTEMPT`, `fake@example.com`, `000.000.000-00`).

**Guia completo:** [`SETUP/README.md`](SETUP/README.md)

---

## Quick Start (projeto já scaffoldado)

### Pré-requisitos

- Python 3.12+
- Docker & Docker Compose
- `make`
- `uv` (Python package manager)

### Setup em um comando

```bash
make setup
```

Instala dependências, copia `.env.example` → `.env`, sobe o stack Docker Compose e roda as migrations.

### Fluxo diário

```bash
make test           # Suite completa (unit + integration)
make lint           # Lint + type-check + secret scan
make deploy-staging # Build → push → deploy para staging
make rollback       # Rollback do último deploy em produção
make docs-serve     # Preview local MkDocs
```

---

## Primeiros Passos após o Clone (Desenvolvedor)

Execute esta checklist **uma única vez** após clonar o repositório, antes de começar a codar.

### 1. Configure o ambiente

```bash
cp .env.example .env
```

Abra `.env` e preencha os valores obrigatórios:

| Variável       | Descrição                                     |
| -------------- | --------------------------------------------- |
| `DATABASE_URL` | URL de conexão com o banco de dados           |
| `LLM_API_KEY`  | Chave de API do provedor LLM                  |
| `SECRET_KEY`   | Chave de segurança da aplicação (>= 32 chars) |
| `REDIS_URL`    | URL do Redis                                  |

> ⚠️ **Nunca commite o `.env`** — ele está no `.gitignore`.

### 2. Suba o stack e instale dependências

```bash
make setup
```

Instala dependências Python (`uv`), sobe o Docker Compose (Postgres, Redis, OTel Collector, Jaeger) e roda as migrations.

### 3. Inicialize o baseline de detecção de secrets

```bash
detect-secrets scan > .secrets.baseline
```

Necessário para que o hook de pre-commit do `detect-secrets` funcione corretamente.

### 4. Leia o contrato de comportamento do AI

```
CLAUDE.md
```

Este arquivo governa todo o desenvolvimento assistido por AI neste repositório. Leitura **obrigatória** antes de usar Claude Code em qualquer tarefa.

### 5. Leia o glossário

```
docs/glossary.md
```

Terminologia canônica do projeto. Em caso de ambiguidade, o glossário prevalece.

### 6. Leia as specs da área em que vai trabalhar

```
specs/system/      ← arquitetura e visão geral
specs/ai/          ← agentes, HITL/HOTL, guardrails
specs/privacy/     ← PII, retenção, DPIA/RIPD
```

**Nenhum código é escrito sem spec referenciada.** Consulte `specs/README.md` para o índice completo.

### 7. Confirme baseline verde antes da primeira alteração

```bash
make test
make lint
```

Se algum teste ou lint falhar antes de você tocar no código, abra uma issue imediatamente — não tente corrigir sem entender a causa.

### 8. Revise as decisões arquiteturais da sua área

```
docs/adr/README.md
```

As ADRs são vinculantes. Qualquer decisão que as contradiga requer uma nova ADR aprovada pelo Tech Lead.

### 9. Verifique os targets de SLO

```
docs/sre/slo/slo.yaml
```

Suas alterações **não devem degradar** nenhum SLO existente. O error budget atual está em `infrastructure/monitoring/grafana/dashboards/sre-overview.json`.

---

## Repository Structure

```
.
├── CLAUDE.md              ← AI behavioral contract
├── docs/                  ← Architecture, ADRs, SRE, Privacy docs
├── specs/                 ← Spec-Driven Development specs
├── src/                   ← Application source code
│   ├── agents/            ← AI agents + HITL gateway
│   ├── guardrails/        ← Safety controls (PII, injection, audit)
│   └── observability/     ← Metrics, logs, traces
├── tests/                 ← Full test pyramid
├── infrastructure/        ← IaC (Terraform, Helm, monitoring)
├── .github/workflows/     ← CI/CD pipelines
└── skills/                ← Claude Code enterprise skills
```

Full annotated tree: [`docs/repo-structure.md`](docs/repo-structure.md)

---

## API

| API Type         | Spec                                 | Description                   |
| ---------------- | ------------------------------------ | ----------------------------- |
| REST (sync)      | `docs/api/openapi/v1/openapi.yaml`   | Synchronous user-facing API   |
| Events (async)   | `docs/api/asyncapi/v1/asyncapi.yaml` | Event-driven async API        |
| gRPC (inter-svc) | `docs/api/grpc/proto/`               | High-performance internal API |

Local API docs:

```bash
make openapi-ui    # Swagger UI at http://localhost:8080
make asyncapi-ui   # AsyncAPI Studio at http://localhost:8081
```

---

## Observability

| Signal                   | Stack                  | Dashboard                                                          |
| ------------------------ | ---------------------- | ------------------------------------------------------------------ |
| Metrics (Golden Signals) | Prometheus + Grafana   | `infrastructure/monitoring/grafana/dashboards/golden-signals.json` |
| SLO / Error Budget       | Prometheus + Grafana   | `infrastructure/monitoring/grafana/dashboards/sre-overview.json`   |
| Traces                   | OpenTelemetry + Jaeger | http://localhost:16686                                             |
| Logs                     | Structured JSON + OTel | Aggregated via OTel Collector                                      |

SLO definitions: [`docs/sre/slo/slo.yaml`](docs/sre/slo/slo.yaml)

---

## On-call

| Resource             | Location                                                                             |
| -------------------- | ------------------------------------------------------------------------------------ |
| Runbooks             | [`docs/runbooks/`](docs/runbooks/)                                                   |
| Rollback procedure   | [`docs/runbooks/rollback-procedure.md`](docs/runbooks/rollback-procedure.md)         |
| Disaster recovery    | [`docs/runbooks/disaster-recovery.md`](docs/runbooks/disaster-recovery.md)           |
| Post-mortem template | [`docs/postmortems/POSTMORTEM-TEMPLATE.md`](docs/postmortems/POSTMORTEM-TEMPLATE.md) |

**Escalation:** On-call → Tech Lead → Engineering Manager

---

## Architecture Decisions

All significant architectural decisions are recorded as ADRs:
[`docs/adr/README.md`](docs/adr/README.md)

Key ADRs:

- [ADR-0001](docs/adr/ADR-0001-monorepo-structure-and-governance.md) — Monorepo structure e governança
- [ADR-0010](docs/adr/ADR-0010-agent-framework-selection.md) — Agent framework selection
- [ADR-0011](docs/adr/ADR-0011-hitl-hotl-model.md) — Human oversight model (HITL/HOTL)
- [ADR-0012](docs/adr/ADR-0012-pii-masking-strategy.md) — PII masking strategy
- [ADR-0013](docs/adr/ADR-0013-data-retention-policy.md) — Data retention policy

---

## AI Governance

This system incorporates AI agents with human oversight controls:

- **HITL** (Human in the Loop): all agent actions with real-world effects require human approval via `src/agents/hitl_gateway.py`
- **HOTL** (Human on the Loop): monitoring and classification flows are autonomous with override capability
- Guardrails: prompt injection defense (LLM01), PII filter (LLM06), action limits (LLM08), immutable audit log (LLM09)

Full AI governance docs: [`docs/ai-governance/`](docs/ai-governance/)

---

## Privacy

This system processes personal data subject to **LGPD** (Brazil) and **GDPR** (EU):

- PII is masked before LLM ingestion, logging, and event publishing
- DPIA and RIPD completed before every production release handling personal data
- Data retention automated per policy

Privacy docs: [`docs/privacy/`](docs/privacy/)

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution guide, branch naming, commit conventions, and PR process.

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community standards.

---

## Security

To report a vulnerability, see [`SECURITY.md`](SECURITY.md).

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).

---

## License

See [`LICENSE`](LICENSE).
