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

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Current circuit breaker state: 0=CLOSED, 0.5=HALF_OPEN, 1=OPEN (REM-014)",
    ["client"],
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

DB_POOL_CONNECTIONS_ACQUIRED = Gauge(
    "db_pool_connections_acquired",
    "Database pool connections currently acquired (in use). "
    "Alert when close to db_pool_size to detect pool exhaustion.",
)

DB_POOL_CONNECTIONS_AVAILABLE = Gauge(
    "db_pool_connections_available",
    "Database pool connections currently idle (available for use).",
)

DLQ_MESSAGES_COUNTER = Counter(
    "dlq_messages_total",
    "Total messages routed to Dead Letter Queue",
    ["consumer_group", "topic"],
)

CONSUMER_HEARTBEAT_TIMESTAMP = Gauge(
    "consumer_heartbeat_timestamp_seconds",
    "Unix epoch of last message committed by the consumer (0 = never). "
    "Alert: time() - this > 300 AND kafka_consumer_lag > 0 (REM-013)",
    ["consumer_group"],
)

# ── Feedback loop metrics ────────────────────────────────────────────────────
# Spec: specs/ai/feedback-loop.md §6

FEEDBACK_REJECTION_RATE = Gauge(
    "agent_feedback_rejection_rate",
    "Observed HITL rejection rate per action type (rolling window)",
    ["action_type"],
)

FEEDBACK_BIAS_APPLIED = Gauge(
    "agent_feedback_bias_applied",
    "Current risk_score bias applied to each action type by the feedback loop",
    ["action_type"],
)

FEEDBACK_ADJUSTMENTS_COUNTER = Counter(
    "agent_feedback_adjustments_total",
    "Total bias adjustments made by the feedback loop",
    ["action_type", "direction"],  # direction: "up" | "down"
)


# ── Agent performance metrics (MTTD / MTTR) ──────────────────────────────────
# Spec: specs/observability/agent-performance.md

_MTTD_BUCKETS = (1, 5, 10, 30, 60, 120, 300, 600)
_MTTR_BUCKETS = (10, 30, 60, 120, 300, 600, 1800, 3600)
_TOKEN_BUCKETS = (100, 500, 1000, 2000, 5000, 10000, 20000, 50000)

AGENT_MTTD_SECONDS = Histogram(
    "agent_mttd_seconds",
    "Time from problem detection to agent action start",
    ["action_type"],
    buckets=_MTTD_BUCKETS,
)

AGENT_MTTR_SECONDS = Histogram(
    "agent_mttr_seconds",
    "Time from agent action start to verified resolution",
    ["action_type"],
    buckets=_MTTR_BUCKETS,
)

AGENT_AUTONOMOUS_RESOLUTION_RATE = Gauge(
    "agent_autonomous_resolution_rate",
    "Fraction of tasks resolved without HITL escalation",
    ["action_type"],
)

AGENT_COST_PER_RESOLUTION_TOKENS = Histogram(
    "agent_cost_per_resolution_tokens",
    "Total LLM tokens consumed per resolved task",
    ["action_type"],
    buckets=_TOKEN_BUCKETS,
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


def record_agent_performance(
    action_type: str,
    mttd_seconds: float,
    mttr_seconds: float,
    resolved_autonomously: bool,
    tokens_used: int,
) -> None:
    AGENT_MTTD_SECONDS.labels(action_type).observe(mttd_seconds)
    AGENT_MTTR_SECONDS.labels(action_type).observe(mttr_seconds)
    AGENT_AUTONOMOUS_RESOLUTION_RATE.labels(action_type).set(1.0 if resolved_autonomously else 0.0)
    if resolved_autonomously:
        AGENT_COST_PER_RESOLUTION_TOKENS.labels(action_type).observe(tokens_used)


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
