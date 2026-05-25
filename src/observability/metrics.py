"""Golden Signals metrics for Prometheus. Provides counters, histograms, and gauges.

Spec: specs/system/architecture.md (Quality Attributes)
ADR:  ADR-0004 (Observability Stack)
Skill: skills/sre/golden-signals.md
"""

from prometheus_client import Counter, Gauge, Histogram

# ── Latency buckets covering the SLO range (p99 ≤ 500ms) ────────────────────
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

# ── Counters ─────────────────────────────────────────────────────────────────
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status_code"],
)

AGENT_ACTIONS_COUNTER = Counter(
    "agent_actions_total",
    "Total agent actions",
    ["agent_id", "action_type", "result"],
)

HITL_APPROVALS_COUNTER = Counter(
    "hitl_approvals_total",
    "Total HITL actions approved by a human reviewer",
    ["agent_id", "action_type"],
)

HITL_REJECTIONS_COUNTER = Counter(
    "hitl_rejections_total",
    "Total HITL actions rejected by a human reviewer",
    ["agent_id", "action_type"],
)

LLM_TOKEN_COUNTER = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["service", "model", "token_type"],
)

# ── Histograms ────────────────────────────────────────────────────────────────
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
    buckets=_LATENCY_BUCKETS,
)

AGENT_ACTION_LATENCY = Histogram(
    "agent_action_duration_seconds",
    "Agent action execution latency in seconds",
    ["agent_id", "action_type"],
    buckets=_LATENCY_BUCKETS,
)

LLM_CALL_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM API call latency in seconds",
    ["service", "model"],
    buckets=_LATENCY_BUCKETS,
)

HITL_WAIT_SECONDS = Histogram(
    "hitl_wait_seconds",
    "Time in seconds a HITL request waited for a human decision",
    ["agent_id"],
    buckets=(60, 300, 600, 900, 1800, 3600),
)

# ── Gauges ────────────────────────────────────────────────────────────────────
KAFKA_CONSUMER_LAG = Gauge(
    "kafka_consumer_lag",
    "Current Kafka consumer lag (messages behind)",
    ["consumer_group", "topic", "partition"],
)

ACTIVE_HITL_REQUESTS = Gauge(
    "hitl_active_requests",
    "Number of HITL requests currently pending human review",
    ["agent_id"],
)

LLM_TOKEN_BUDGET = Gauge(
    "llm_tokens_budget_total",
    "Configured LLM token monthly budget",
    ["service"],
)

AGENT_SEMAPHORE_WAITING = Gauge(
    "agent_semaphore_waiting",
    "Requests currently waiting for an available agent slot",
    ["service"],
)

DLQ_MESSAGES_COUNTER = Counter(
    "dlq_messages_total",
    "Total messages routed to Dead Letter Queue",
    ["consumer_group", "topic"],
)


# ── Initialisation helpers ───────────────────────────────────────────────────


def init_budget_gauge(service: str, monthly_token_budget: int) -> None:
    """Set the static LLM token budget gauge once at startup."""
    LLM_TOKEN_BUDGET.labels(service).set(monthly_token_budget)


# ── Helper functions ─────────────────────────────────────────────────────────


def record_request(
    service: str,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    REQUEST_COUNTER.labels(service, method, path, str(status_code)).inc()
    REQUEST_LATENCY.labels(service, method, path).observe(duration_seconds)


def record_agent_action(
    agent_id: str,
    action_type: str,
    result: str,
    duration_seconds: float,
) -> None:
    AGENT_ACTIONS_COUNTER.labels(agent_id, action_type, result).inc()
    AGENT_ACTION_LATENCY.labels(agent_id, action_type).observe(duration_seconds)


def record_hitl_decision(
    agent_id: str,
    action_type: str,
    approved: bool,
    wait_seconds: float,
) -> None:
    if approved:
        HITL_APPROVALS_COUNTER.labels(agent_id, action_type).inc()
    else:
        HITL_REJECTIONS_COUNTER.labels(agent_id, action_type).inc()
    HITL_WAIT_SECONDS.labels(agent_id).observe(wait_seconds)
    ACTIVE_HITL_REQUESTS.labels(agent_id).dec()


def record_llm_call(
    service: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float,
) -> None:
    LLM_TOKEN_COUNTER.labels(service, model, "input").inc(input_tokens)
    LLM_TOKEN_COUNTER.labels(service, model, "output").inc(output_tokens)
    LLM_CALL_LATENCY.labels(service, model).observe(duration_seconds)
