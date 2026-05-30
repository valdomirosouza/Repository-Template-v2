# Quickstart — Python Backend

> **Stack:** Python 3.13 · FastAPI · asyncpg · aiokafka · OpenTelemetry · Anthropic SDK
> **Service types:** REST API, AI agent orchestrator, Kafka consumer
> **Read first:** [docs/quickstart/README.md](README.md) for shared governance rules.

---

## Prerequisites

| Tool             | Version | Install                                                                 |
| ---------------- | ------- | ----------------------------------------------------------------------- |
| Python           | 3.13+   | [python.org](https://www.python.org/downloads/) or `pyenv install 3.13` |
| uv               | latest  | `curl -LsSf https://astral.sh/uv/install.sh \| sh`                      |
| Docker & Compose | 24+     | [docker.com](https://www.docker.com/products/docker-desktop/)           |
| make             | any     | pre-installed on macOS/Linux                                            |
| kubectl          | 1.28+   | `brew install kubectl`                                                  |
| helm             | 3.x     | `brew install helm`                                                     |

---

## Which files are yours

```
src/                          ← your application code lives here
├── agents/                   ← AI agent logic (HITL gateway, orchestrator, harness)
├── api/rest/                 ← FastAPI routers, middleware, lifespan
├── guardrails/               ← PII filter, injection guard, audit logger, action limits
├── observability/            ← OTel setup, Prometheus metrics, structured logger
└── shared/                   ← config, models, retry, db client, feature flags

tests/
├── unit/                     ← fast, no I/O (pytest, no external services)
└── integration/              ← real services via docker-compose.test.yml

infrastructure/k8s/           ← Kubernetes manifests for your service
infrastructure/feature-flags/ ← flagd configuration (autonomous-mode flag)
```

**Files you do NOT own (shared contracts — read-only):**

```
docs/api/openapi/       ← REST contract — generate your stubs from this
docs/api/asyncapi/      ← Kafka event contract — do not hand-write consumers
docs/api/grpc/proto/    ← gRPC definitions — generate from proto files
infrastructure/message-broker/schema-registry/avro/  ← Avro schemas
```

---

## Setup

```bash
# 1. Install Python dependencies
uv sync

# 2. Copy and configure environment
cp .env.example .env
# Required fields — edit before running:
#   DATABASE_URL      postgresql+asyncpg://user:password@localhost:5432/dbname
#   REDIS_URL         redis://localhost:6379/0
#   ANTHROPIC_API_KEY your-api-key-here
#   SECRET_KEY        minimum-32-character-secret

# 3. Start shared infrastructure
docker compose up -d

# 4. Run database migrations
uv run alembic upgrade head

# 5. Confirm baseline is green
make test-python
make lint-python
```

Expected output: all tests pass, no lint violations.

---

## Daily workflow

```bash
make test-python          # unit + integration tests with coverage
make test-unit-python     # unit only (fast, no Docker required)
make lint-python          # ruff + mypy + detect-secrets
make format-python        # auto-format with ruff
make run                  # start FastAPI dev server (hot-reload)
```

---

## Key architectural patterns

### Config — never hardcode values

All configuration comes from environment variables via Pydantic Settings:

```python
from src.shared.config import settings

# Use settings.* — never os.environ.get() directly
timeout = settings.llm_call_timeout_seconds
```

Add new settings to `src/shared/config.py`. Never use `os.environ.get()` directly in service code.

### Resilience — always use the wrappers

```python
from src.shared.retry import with_retry, CircuitBreaker
from src.shared.db_client import ResilientDBPool

# Every external call gets timeout + retry + circuit breaker
# See src/shared/retry.py for CircuitBreaker and with_retry decorator
```

Do not call `asyncpg` or `redis` directly. Use `ResilientDBPool` and the existing Redis client wrappers.

### PII — mask before everything

```python
from src.guardrails.pii_filter import mask_dict, mask_text

# Before any log write, LLM call, or Kafka publish:
safe_payload = mask_dict(raw_payload)
logger.info("Processing request", **safe_payload)
```

See `specs/ai/guardrails.md` and `docs/privacy/pii-inventory.md` for classification levels.

### Agent actions — always route through HITL

```python
from src.agents.hitl_gateway import HITLGateway, HITLRequest

# Any action with real-world effect MUST go through the gateway
# It will check the risk_score against settings.hitl_risk_threshold
# and route to human approval when needed (unless autonomous-mode is on)
```

HITL/HOTL model: `docs/adr/ADR-0011-hitl-hotl-model.md`

### Feature flags — use OpenFeature

```python
from src.shared.feature_flags import is_autonomous_mode_enabled

if is_autonomous_mode_enabled():
    # HOTL path — agent acts without HITL
else:
    # HITL path — human approval required
```

Flags live in `infrastructure/feature-flags/flags/`. Never use `if settings.autonomous_mode_enabled` directly — always go through `feature_flags.py`.

---

## Observability

Every service must emit the four Golden Signals:

```python
from src.observability.metrics import (
    REQUEST_COUNTER,
    REQUEST_LATENCY,
    AGENT_ACTIONS_COUNTER,
)

# Record in your route handler or middleware
REQUEST_COUNTER.labels(method="POST", path="/v1/requests", status_code=202).inc()
REQUEST_LATENCY.labels(method="POST", path="/v1/requests").observe(duration)
```

OTel tracing is bootstrapped in `src/observability/otel_setup.py` and activated in `src/api/rest/main.py`. Your routes are automatically instrumented via `FastAPIInstrumentor`.

Logs must use the structured logger — never `print()`:

```python
from src.observability.logger import get_logger

logger = get_logger("my-component")
logger.info("Processing item", item_id=str(item_id), trace_id=trace_id)
```

---

## Testing conventions

```python
# Unit test — no I/O, mock all external dependencies
@pytest.mark.unit
async def test_my_function(monkeypatch):
    ...

# Integration test — uses docker-compose.test.yml services
@pytest.mark.integration
async def test_my_integration():
    ...

# Security test — guardrail validation
@pytest.mark.security
async def test_no_pii_leakage():
    ...
```

Coverage must be ≥ 80% before merge. CI enforces this.

---

## HITL integration (REST client for other languages)

If your Python service calls another service's HITL endpoint, use the internal REST API:

```
POST /v1/hitl/requests       — submit action for approval
GET  /v1/hitl/requests/{id}  — poll for decision
POST /v1/hitl/decisions      — record approve/reject (human UI)
```

Full spec: `docs/api/openapi/v1/openapi.yaml` — `/v1/hitl` paths.

---

## Deployment

```bash
# Build image
make build-python

# Deploy to staging
make deploy-staging SERVICE=api-gateway

# Check health
curl http://staging.internal/health
curl http://staging.internal/ready
```

K8s manifests: `infrastructure/k8s/` — do not modify `deployment.yaml` probe configuration
without reviewing `docs/runbooks/RB-003-hitl-recovery.md`.

---

## Key ADRs for Python developers

| ADR                                                         | Why it matters to you                   |
| ----------------------------------------------------------- | --------------------------------------- |
| [ADR-0002](../adr/ADR-0002-technology-stack-selection.md)   | FastAPI, asyncpg, aiokafka rationale    |
| [ADR-0010](../adr/ADR-0010-agent-framework-selection.md)    | Why the agent framework was chosen      |
| [ADR-0011](../adr/ADR-0011-hitl-hotl-model.md)              | HITL gateway — when and why             |
| [ADR-0014](../adr/ADR-0014-multi-agent-harness-strategy.md) | Multi-agent harness (Planner/Evaluator) |
| [ADR-0015](../adr/ADR-0015-feature-flag-strategy.md)        | Feature flags — OpenFeature SDK usage   |
