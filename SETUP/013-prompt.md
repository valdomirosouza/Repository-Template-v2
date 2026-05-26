# Prompt 013 — Resilience, Persistence & Platform Maturity Layer

> **Requires:** Prompts 001–010 completed (base scaffold must exist).
> Reference: `MONOREPO-STRUCTURE-EN.md` (Section "SOURCE CODE" → `shared/` and `agents/`).
> Reference: ADR-0011 (HITL/HOTL), ADR-0014 (Harness), ADR-0015 (Feature Flags).
> Skip any file that already exists with real content.
>
> This prompt adds the **resilience and platform maturity layer** introduced in the
> Harness Engineering Audit remediation (P1/P2/P3 waves). It does not modify guardrails
> or security files — those remain the sole responsibility of Prompt 010.

---

## Task

Create the following files with **real, production-quality Python and YAML**.
All Python files must be type-annotated, PEP 8-compliant, and include module-level
docstrings with `Spec:` and `ADR:` references. No real credentials, no real PII.

---

## `src/shared/retry.py`

Retry, circuit breaker, and resilient LLM client wrapper.

```
Spec: specs/system/architecture.md
ADR:  ADR-0014 (Multi-Agent Harness Strategy)
```

Implement:

```python
class TransientError(Exception):
    """Raised to signal a transient failure eligible for retry."""

class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is OPEN and rejecting calls."""

class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Three-state circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None: ...

    async def call(self, coro: Awaitable[T]) -> T:
        """Execute coro under circuit breaker protection. Raises CircuitBreakerError when OPEN."""

    @property
    def state(self) -> CircuitState: ...

def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: float = 2.0,
) -> Callable:
    """
    Decorator — wraps an async function with tenacity exponential backoff + jitter.
    Uses wait_exponential(min=min_wait, max=max_wait) + wait_random(0, jitter).
    Retries only on TransientError; all other exceptions propagate immediately.
    """

class ResilientLLMClientWrapper:
    """Composes: asyncio.wait_for timeout → CircuitBreaker → with_retry."""
    def __init__(
        self,
        client: LLMClient,
        timeout_seconds: float,
        circuit_breaker: CircuitBreaker,
    ) -> None: ...

    async def complete(self, system: str, user: str, trace_id: str | None = None) -> str: ...
```

- Import `LLMClient` from `src/shared/llm_client.py`
- Import timeout from `src/shared/config.py` (`settings.llm_call_timeout_seconds`)
- Log circuit state transitions via `src/observability/logger.py`

---

## `src/shared/db_client.py`

Resilient asyncpg connection pool with circuit breaker and retry.

```
Spec: specs/system/architecture.md
ADR:  ADR-0002 (Technology Stack Selection)
```

Implement:

```python
class ResilientDBPool:
    """
    Wraps asyncpg.Pool with per-call asyncio.wait_for timeout,
    exponential-backoff retry, and a three-state circuit breaker.
    """
    def __init__(self, pool: asyncpg.Pool, timeout: float = 5.0) -> None: ...

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute SELECT and return one row. Raises TransientError on timeout."""

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute scalar SELECT. Used by /ready health check."""

    async def execute(self, query: str, *args: Any) -> str:
        """Execute INSERT/UPDATE/DELETE. Raises AuditWriteError on failure (via caller)."""

    async def acquire(self) -> asyncpg.Connection:
        """
        Return a raw connection for transaction management.
        Bypasses circuit breaker — transaction callers are responsible for their own error handling.
        """

async def create_resilient_pool(dsn: str, **kwargs: Any) -> ResilientDBPool:
    """
    Create asyncpg pool wrapped in ResilientDBPool.
    kwargs forwarded to asyncpg.create_pool (min_size, max_size, etc.).
    """
```

- All methods except `acquire()` route through `@with_retry()` and `CircuitBreaker`
- Wrap each pool call in `asyncio.wait_for(timeout=self._timeout)`
- Raise `TransientError` on `asyncio.TimeoutError` and `asyncpg.PostgresConnectionError`
- Log every circuit state change

---

## `src/shared/feature_flags.py`

OpenFeature SDK wrapper for feature flag evaluation.

```
Spec: specs/system/architecture.md
ADR:  ADR-0015 (Feature Flag Strategy)
```

Implement:

```python
def is_autonomous_mode_enabled() -> bool:
    """
    Return True if the 'autonomous-mode' feature flag is enabled.

    Evaluation order:
    1. OpenFeature SDK (flagd provider in production, InMemoryProvider in tests).
    2. settings.autonomous_mode_enabled fallback (if SDK raises or is not configured).
    """
    try:
        from openfeature import api  # optional dep — openfeature-sdk
        client = api.get_client()
        return client.get_boolean_value("autonomous-mode", settings.autonomous_mode_enabled)
    except Exception:
        return settings.autonomous_mode_enabled
```

- Import `settings` from `src/shared/config.py`
- The try/except must catch ALL exceptions — SDK unavailability must never crash the app
- Add a module docstring explaining the fallback behaviour and linking to ADR-0015

---

## `src/api/rest/_limiter.py`

Shared slowapi rate limiter singleton.

```
Spec: specs/api/async-api-design.md
ADR:  ADR-0002 (Technology Stack Selection)
```

Implement:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

- Module-level singleton imported by routers
- `key_func=get_remote_address` keys rate limits by client IP

---

## `src/agents/hitl_store.py`

Pluggable HITL request persistence — Protocol + two implementations.

```
Spec: specs/ai/hitl-hotl.md
ADR:  ADR-0011 (HITL/HOTL Human Oversight Model)
```

Implement the following three items:

### `HITLStore` Protocol

```python
class HITLStore(Protocol):
    async def save(self, request: HITLRequest) -> None: ...
    async def get(self, request_id: str) -> HITLRequest | None:
        """Return request from active or archived store. None if not found."""
    async def get_active(self, request_id: str) -> HITLRequest | None:
        """Return request only if still in active (non-archived) store."""
    async def pending_count(self) -> int: ...
    async def get_pending_expired(self, now: datetime) -> list[HITLRequest]:
        """Return PENDING requests whose expires_at < now."""
    async def evict(self, request_id: str) -> None:
        """Remove from active store without archiving (for capacity eviction)."""
    async def archive(self, request_id: str, request: HITLRequest) -> None:
        """Move from active to archive (for expiry / decision recording)."""
```

### `InMemoryHITLStore`

In-memory implementation using two dicts: `_active` and `_archived`.

- `save` → stores in `_active`
- `get` → checks `_active` first, then `_archived`
- `get_active` → checks only `_active`
- `pending_count` → counts entries in `_active` where `status == PENDING`
- `get_pending_expired` → filters `_active` for `PENDING` entries with `expires_at < now`
- `evict` → removes from `_active` without touching `_archived`
- `archive` → removes from `_active`, inserts into `_archived`

### `HITLRedisStore`

Redis-backed implementation with TTL and sorted-set expiry tracking.

Key schema:

```
hitl:req:{request_id}     → JSON blob (TTL = expires_at + grace_hours * 3600)
hitl:pending              → Sorted Set; score = expires_at.timestamp(); member = request_id
hitl:expired:{request_id} → JSON blob (TTL = expired_days * 86400)
```

Constructor parameters:

```python
def __init__(
    self,
    client: redis.asyncio.Redis,
    key_prefix: str = "hitl",
    grace_hours: int = 24,
    expired_days: int = 7,
) -> None
```

Key methods:

- `save` → pipeline: SET with TTL + ZADD to sorted set
- `get` → checks `hitl:req:{id}` first, then `hitl:expired:{id}`
- `get_active` → checks only `hitl:req:{id}`
- `pending_count` → ZCARD on `hitl:pending`
- `get_pending_expired` → ZRANGEBYSCORE(`-inf`, `now.timestamp()`) → fetch each `hitl:req:{id}` → filter `status == PENDING`
- `evict` → pipeline: ZREM from sorted set + DEL `hitl:req:{id}`
- `archive` → pipeline: ZREM + DEL `hitl:req:{id}` + SET `hitl:expired:{id}` with TTL

Serialization: JSON with `datetime` as ISO-8601 string and `HITLStatus` as string value.

**Import note:** `HITLRequest` and `HITLStatus` are imported from `src/agents/hitl_gateway.py`.
To avoid circular imports, `hitl_store.py` must NOT be imported at module level by
`hitl_gateway.py` — the gateway uses a lazy import inside `__init__`.

---

## Infrastructure — Kubernetes Manifests

### `infrastructure/k8s/deployment.yaml`

K8s Deployment for agent-service with:

- All three probe types:
  - `startupProbe`: `httpGet /health`, `failureThreshold: 30`, `periodSeconds: 10`
  - `livenessProbe`: `httpGet /health`, `initialDelaySeconds: 5`
  - `readinessProbe`: `httpGet /ready`, `initialDelaySeconds: 10`
- `lifecycle.preStop.exec`: `["sleep", "5"]`
- `terminationGracePeriodSeconds: 30`
- `strategy.rollingUpdate`: `maxSurge: 1`, `maxUnavailable: 0`
- `resources.requests`: `cpu: "250m"`, `memory: "256Mi"`
- `resources.limits`: `cpu: "1000m"`, `memory: "512Mi"`
- Env vars from `secretKeyRef` for: `DATABASE_URL`, `REDIS_URL`, `ANTHROPIC_API_KEY`, `SECRET_KEY`
- Image: `ghcr.io/org/template-service:latest` (placeholder)

### `infrastructure/k8s/service.yaml`

ClusterIP Service exposing port 8000 → containerPort 8000, named `http`.

### `infrastructure/k8s/pdb.yaml`

PodDisruptionBudget with `minAvailable: 2` — prevents zero-replica windows during node drains.

### `infrastructure/k8s/hpa.yaml`

HorizontalPodAutoscaler with:

- `minReplicas: 2`, `maxReplicas: 10`
- CPU: `averageUtilization: 70`
- Custom Pods metric: `agent_semaphore_waiting`, `AverageValue: "3"`
- Custom Object metric: `kafka_consumer_lag`, `Value: "5000"`, describedObject: `Service/kafka`
- `behavior.scaleUp.stabilizationWindowSeconds: 60`
- `behavior.scaleDown.stabilizationWindowSeconds: 300`

### `infrastructure/k8s/prometheus-adapter-config.yaml`

ConfigMap `prometheus-adapter-config` in namespace `monitoring` with rules mapping:

- `agent_semaphore_waiting{namespace!="",pod!=""}` → `avg(<<.Series>>{<<.LabelMatchers>>})`
- `kafka_consumer_lag{namespace!=""}` → `sum(<<.Series>>{<<.LabelMatchers>>})`

---

## Infrastructure — Feature Flags

### `infrastructure/feature-flags/flagd.yaml`

Three K8s resources in a single file (separated by `---`):

1. **ConfigMap** `flagd-flags`: data key `autonomous-mode.yaml` with the flag YAML content.

2. **Deployment** `flagd`:
   - Image: `ghcr.io/open-feature/flagd:latest`
   - Args: `["start", "--uri", "file:///etc/flagd/flags/autonomous-mode.yaml"]`
   - Volume mount: ConfigMap mounted at `/etc/flagd/flags/`
   - Port 8013 (gRPC), port 8014 (HTTP/OFREP)
   - Resources: `requests: {cpu: 50m, memory: 64Mi}`, `limits: {cpu: 200m, memory: 128Mi}`

3. **Service** `flagd`: ClusterIP, ports 8013 and 8014.

### `infrastructure/feature-flags/flags/autonomous-mode.yaml`

```yaml
flags:
  autonomous-mode:
    state: ENABLED
    variants:
      "on": true
      "off": false
    defaultVariant: "off"
    targeting: {}
```

---

## Alembic — Database Migrations

### `alembic.ini`

Standard Alembic configuration pointing to `alembic/` directory.
Set `script_location = alembic`.
Leave `sqlalchemy.url` empty — it is set programmatically in `alembic/env.py`.

### `alembic/env.py`

```python
from src.shared.config import settings

config.set_main_option("sqlalchemy.url", settings.database_url)
```

Async-compatible: use `asyncio.run(run_async_migrations())` pattern with `AsyncEngine`.

### `alembic/versions/0001_create_audit_events.py`

Migration creating `audit_events` table:

```sql
CREATE TABLE audit_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  VARCHAR(100) NOT NULL,
    agent_id    VARCHAR(255),
    action      VARCHAR(255) NOT NULL,
    outcome     VARCHAR(50)  NOT NULL,
    risk_score  FLOAT,
    metadata    JSONB        DEFAULT '{}',
    trace_id    VARCHAR(255),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_events_agent_id    ON audit_events (agent_id);
CREATE INDEX idx_audit_events_created_at  ON audit_events (created_at DESC);

REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC;
```

---

## Chaos Engineering Experiments

### `tests/chaos/experiments/kill-agent.yaml`

Chaos Toolkit experiment that:

1. Verifies `/health` and `/ready` return 200 (steady-state before)
2. Action: terminate the `agent-service` pod via `kubectl delete pod`
3. Pauses 15s for K8s to reschedule
4. Verifies `/health` and `/ready` return 200 (steady-state after)

Use `chaostoolkit` YAML format with `steady-state-hypothesis`, `method`, and `rollbacks` sections.

### `tests/chaos/experiments/broker-outage.yaml`

Chaos Toolkit experiment that:

1. Verifies Kafka consumer lag metric is below threshold (steady-state)
2. Action: scale Kafka StatefulSet to 0 replicas (`kubectl scale statefulset kafka --replicas=0`)
3. Pauses 30s
4. Rollback: scale back to 1 replica
5. Verifies consumer lag recovers

### `tests/chaos/experiments/network-partition.yaml`

Chaos Toolkit experiment that:

1. Verifies DLQ depth is 0 (steady-state before)
2. Action: apply a NetworkPolicy blocking agent → Kafka traffic
3. Pauses 20s (traffic should route to DLQ)
4. Rollback: delete the NetworkPolicy
5. Verifies DLQ depth returns to 0 within 60s

---

## Integration Tests

### `tests/integration/test_hitl_redis_store.py`

Integration tests for `HITLRedisStore` using `fakeredis.FakeAsyncRedis(decode_responses=True)`.

Test cases (minimum):

- `test_save_and_get_roundtrip` — save a request, get it back, fields match
- `test_get_active_returns_none_after_archive` — archive a request, get_active returns None
- `test_get_returns_archived_request` — archive a request, get() finds it in archive
- `test_pending_count_reflects_active_only` — only PENDING active requests counted
- `test_get_pending_expired_filters_by_time` — returns only requests past expires_at
- `test_get_pending_expired_excludes_approved` — APPROVED requests not in result
- `test_evict_removes_from_active` — evict removes from active and sorted set
- `test_archive_moves_to_expired_key` — archive sets `hitl:expired:{id}` key

Fixture:

```python
@pytest.fixture
async def client():
    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield r
    await r.aclose()
```

---

## Validation

After creating all files, confirm:

- [ ] `src/shared/retry.py` exports `CircuitBreaker`, `with_retry`, `ResilientLLMClientWrapper`
- [ ] `src/shared/db_client.py` exports `ResilientDBPool`, `create_resilient_pool`
- [ ] `src/shared/feature_flags.py` exports `is_autonomous_mode_enabled`; fallback to `settings.autonomous_mode_enabled` on any exception
- [ ] `src/api/rest/_limiter.py` exports `limiter` singleton
- [ ] `src/agents/hitl_store.py` exports `HITLStore` (Protocol), `InMemoryHITLStore`, `HITLRedisStore`
- [ ] `HITLRedisStore` does NOT import at module level from `hitl_gateway.py` (would cause circular import)
- [ ] All 5 K8s manifests are valid YAML (run `kubectl apply --dry-run=client -f infrastructure/k8s/`)
- [ ] `flagd.yaml` contains three resources: ConfigMap + Deployment + Service
- [ ] `flags/autonomous-mode.yaml` has `defaultVariant: "off"`
- [ ] `alembic/versions/0001_create_audit_events.py` includes `REVOKE UPDATE, DELETE`
- [ ] All three chaos experiments have `steady-state-hypothesis` sections
- [ ] `tests/integration/test_hitl_redis_store.py` uses `fakeredis.FakeAsyncRedis(decode_responses=True)`
- [ ] No real credentials, no real PII in any file
