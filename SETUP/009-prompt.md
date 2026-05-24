# Prompt 009 — Source Code (Agents, Observability, Shared)

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section "SOURCE CODE").
> Skip any file that already exists with real content.
> **No guardrail files in this prompt** — those are handled in Prompt 010.

---

## Task

Create the following source code files with **real, production-quality Python**.
All files must be type-annotated, follow PEP 8, and include module-level docstrings.
Use only synthetic data in any examples or defaults. No real credentials.

---

## `src/agents/hitl_gateway.py`

HITL Gateway — mandatory approval flow for agent actions with real-world effects.

Implement:

```python
# Required classes and functions (implement fully):

@dataclass
class HITLRequest:
    request_id: str          # UUID
    agent_id: str
    action_type: str
    action_parameters: dict
    risk_score: float        # 0.0 – 1.0
    context_summary: str     # PII-masked summary for the human reviewer
    created_at: datetime
    expires_at: datetime     # created_at + HITL_APPROVAL_TIMEOUT_SECONDS
    status: HITLStatus       # Enum: PENDING / APPROVED / REJECTED / EXPIRED

@dataclass
class HITLDecision:
    request_id: str
    decision: HITLStatus     # APPROVED or REJECTED
    approver_id: str
    rationale: str
    decided_at: datetime

class HITLGateway:
    async def submit_for_approval(self, request: HITLRequest) -> HITLRequest
    async def record_decision(self, decision: HITLDecision) -> HITLRequest
    async def get_request(self, request_id: str) -> HITLRequest | None
    async def expire_stale_requests(self) -> list[str]   # returns expired request IDs
    def _is_expired(self, request: HITLRequest) -> bool
```

- `submit_for_approval` publishes a `agent.action.proposed` event to the broker
  and persists the request; returns the created request
- `record_decision` validates the request exists and is PENDING, records the decision,
  publishes `agent.action.approved` or `agent.action.rejected` event
- `expire_stale_requests` is called periodically; marks PENDING requests past `expires_at`
  as EXPIRED; never auto-approves
- All methods log via `src/observability/logger.py` (PII-masked context only)
- All state changes emit metrics via `src/observability/metrics.py`
- Import and use `src/guardrails/audit_logger.py` to record every decision

---

## `src/observability/otel_setup.py`

OpenTelemetry SDK bootstrap. Implement:

```python
def setup_telemetry(service_name: str, service_version: str) -> None:
    """
    Initialise OpenTelemetry tracing, metrics, and logging exporters.
    Call once at application startup before any other instrumentation.
    """
```

- Configure `OTLPSpanExporter` pointing to `OTEL_EXPORTER_OTLP_ENDPOINT`
- Configure `BatchSpanProcessor`
- Set `Resource` with `service.name`, `service.version`, `deployment.environment`
- Configure `OTLPMetricExporter` with delta temporality
- Configure `PeriodicExportingMetricReader` (interval 60s)
- Set global `TracerProvider` and `MeterProvider`
- Configure W3C `TraceContextPropagator` + `BagagePropagator` as composite propagator
- Read all endpoints and service identity from `src/shared/config.py`
- Graceful shutdown: register `atexit` handler to flush exporters

---

## `src/observability/metrics.py`

Prometheus Golden Signals metrics. Implement using `prometheus_client`:

```python
# Counters
REQUEST_COUNTER         # labels: service, method, path, status_code
AGENT_ACTIONS_COUNTER   # labels: agent_id, action_type, result (success/failure/rejected)
HITL_APPROVALS_COUNTER  # labels: agent_id, action_type
HITL_REJECTIONS_COUNTER # labels: agent_id, action_type
LLM_TOKEN_COUNTER       # labels: service, model, token_type (input/output)

# Histograms
REQUEST_LATENCY         # labels: service, method, path — buckets: .005,.01,.025,.05,.1,.25,.5,1,2.5,5
AGENT_ACTION_LATENCY    # labels: agent_id, action_type
LLM_CALL_LATENCY        # labels: service, model

# Gauges
KAFKA_CONSUMER_LAG      # labels: consumer_group, topic, partition
ACTIVE_HITL_REQUESTS    # labels: agent_id
```

Provide helper functions:

- `record_request(method, path, status_code, duration_seconds)`
- `record_agent_action(agent_id, action_type, result, duration_seconds)`
- `record_hitl_decision(agent_id, action_type, approved: bool)`
- `record_llm_call(service, model, input_tokens, output_tokens, duration_seconds)`

---

## `src/observability/logger.py`

Structured JSON logger with PII masking. Implement:

```python
class StructuredLogger:
    def __init__(self, service: str, component: str): ...

    def info(self, message: str, **context) -> None: ...
    def warning(self, message: str, **context) -> None: ...
    def error(self, message: str, exc_info: bool = False, **context) -> None: ...
    def audit(self, event: str, **context) -> None: ...  # severity AUDIT — never masked
```

- Every log record is a JSON object with:
  `timestamp` (ISO 8601), `severity`, `service`, `component`, `message`,
  `trace_id`, `span_id` (extracted from current OTel context), plus all `**context` fields
- **Before writing any log record**, pass all `**context` values through
  `src/guardrails.pii_filter.mask_dict()` to replace PII with tokens
- `audit()` method writes to a separate audit log stream; context fields are NOT
  masked (audit logs may contain identifiers for legal traceability — document this)
- Use `structlog` or `logging` + JSON formatter; default to `logging`
- Log level controlled by `LOG_LEVEL` env var from `src/shared/config.py`

Provide a module-level `get_logger(component: str) -> StructuredLogger` factory.

---

## `src/shared/config.py`

Pydantic Settings with all environment variables. Implement:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App core
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"
    service_name: str = "template-service"
    service_version: str = "0.1.0"

    # Database
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "template-consumer-group"
    kafka_schema_registry_url: str = "http://localhost:8081"

    # LLM / AI
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    llm_api_key: str
    llm_max_tokens: int = 4096
    llm_token_budget_per_request: int = 2000
    hitl_approval_timeout_seconds: int = 300

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "template-service"
    prometheus_port: int = 9090
    jaeger_agent_host: str = "localhost"

    # Feature flags
    feature_flag_provider: str = "local"
    feature_flag_sdk_key: str = ""
    autonomous_mode_enabled: bool = False

    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 3600
    allowed_origins: list[str] = ["http://localhost:3000"]
    rate_limit_requests_per_minute: int = 60

    # Privacy
    pii_masking_enabled: bool = True
    pii_audit_log_enabled: bool = True
    data_retention_days: int = 30

    # FinOps
    llm_monthly_token_budget: int = 1_000_000
    cost_alert_threshold_usd: float = 100.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Module-level singleton
settings = Settings()
```

---

## `src/shared/models.py`

Base domain models using Pydantic v2. Implement:

```python
class BaseModel(PydanticBaseModel):
    """All domain models inherit from this. Adds created_at, updated_at, id."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

class AgentActionRequest(BaseModel):
    agent_id: str
    action_type: str
    parameters: dict
    risk_score: float = Field(ge=0.0, le=1.0)
    requires_hitl: bool = True
    context: dict = Field(default_factory=dict)

class AgentActionResult(BaseModel):
    request_id: UUID
    agent_id: str
    action_type: str
    status: str       # completed / rejected / failed / pending_hitl
    output: dict = Field(default_factory=dict)
    error: str | None = None
    hitl_decision: str | None = None

class AuditEvent(BaseModel):
    event_type: str
    agent_id: str | None = None
    user_id: str | None = None   # anonymised internal ID — not PII L1/L2
    action: str
    outcome: str
    metadata: dict = Field(default_factory=dict)
    trace_id: str | None = None
```

---

## `src/guardrails/action_limits.py`

Agent action rate limits and scope limits. Implement:

```python
@dataclass
class ActionLimitConfig:
    agent_id: str
    max_actions_per_minute: int
    max_actions_per_hour: int
    allowed_action_types: list[str]
    max_records_affected: int      # max rows/items one action may touch
    allowed_environments: list[str]  # e.g. ["staging", "production"]

class ActionLimiter:
    def __init__(self, config: ActionLimitConfig, redis_client): ...

    async def check_rate_limit(self, agent_id: str, action_type: str) -> bool:
        """Returns True if action is within rate limits. Uses Redis sliding window."""

    def check_scope_limit(
        self, agent_id: str, action_type: str, parameters: dict
    ) -> tuple[bool, str]:
        """
        Returns (allowed, reason). Checks action_type is in allowed list
        and affected record count is within max_records_affected.
        """

    async def record_action(self, agent_id: str, action_type: str) -> None:
        """Increment counters in Redis. Called after a successful action."""
```

- Rate limit uses Redis sliding window counter (key: `limits:{agent_id}:{window}`)
- Scope check validates `action_type` against `allowed_action_types`
- Both checks log decisions via `src/observability/logger.py`
- Config loaded from `src/shared/config.py` or passed explicitly

---

## `src/guardrails/audit_logger.py`

Immutable audit log for all agent actions. Implement:

```python
class AuditLogger:
    def __init__(self, storage_backend: AuditStorage): ...

    async def log_event(self, event: AuditEvent) -> str:
        """
        Append audit event to immutable log. Returns event ID.
        Raises AuditWriteError if write fails — callers must treat this as
        a hard failure and block the associated action.
        """

    async def query_events(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]: ...
```

- `AuditEvent` imported from `src/shared/models.py`
- Append-only: storage backend must enforce no-update, no-delete semantics
- Every event includes: `event_id` (UUID), `timestamp`, `agent_id`, `action_type`,
  `outcome`, `approver_id` (for HITL decisions), `trace_id`
- `AuditStorage` protocol with `append(event)` and `query(filters)` methods;
  provide `InMemoryAuditStorage` for testing and a `PostgresAuditStorage` stub
- Log every write attempt (success or failure) via `src/observability/logger.py`

---

### Validation

After creating all files, confirm:

- All 7 files exist with complete, type-annotated Python code
- `src/agents/hitl_gateway.py` imports `audit_logger` and `metrics`
- `src/observability/logger.py` calls `pii_filter.mask_dict()` before writing
  (import is present even though `pii_filter.py` is created in Prompt 010)
- `src/shared/config.py` exports a module-level `settings` singleton
- `src/guardrails/audit_logger.py` raises an error on write failure
  (never silently swallows it)
- No real credentials, no real PII in any file
