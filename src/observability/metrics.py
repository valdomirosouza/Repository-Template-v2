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
    # NOTE: do NOT add request_id / trace_id as a label — it is unbounded and creates a new
    # time series per request, which OOMs Prometheus under load (W1-4). Per-request token cost
    # is carried on the OTel `llm.inference` span (gen_ai.usage.*) instead, where the trace_id
    # already lives — that is the correct place to drill down by request.
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


# ── Sub-agent specialization metrics (Issue #6) ───────────────────────────────
# Spec: specs/ai/sub-agent-specialization.md §5 | ADR: ADR-0032

AGENT_SUBTASK_DURATION = Histogram(
    "agent_subtask_duration_seconds",
    "Execution latency per sub-agent specialization",
    ["agent_role", "harness_mode"],
    buckets=_LATENCY_BUCKETS,
)

AGENT_SUBTASK_ERROR_COUNTER = Counter(
    "agent_subtask_error_total",
    "Error count per sub-agent specialization and error class",
    ["agent_role", "error_type"],
)

# ── Agent productivity metrics (Issue #7) ────────────────────────────────────
# Spec: specs/ai/long-running-session.md §2.1 | ADR: ADR-0020 Appendix

_CYCLE_TIME_BUCKETS = (60, 300, 600, 1800, 3600, 7200, 14400, 86400)
_SESSION_DURATION_BUCKETS = (60, 300, 600, 1800, 3600, 7200, 14400)

AGENT_SESSION_TASKS_COUNTER = Counter(
    "agent_session_tasks_total",
    "Tasks completed per session, broken down by type and outcome",
    # task_type: planned|net_new|papercut|tech_debt; outcome: completed|abandoned
    ["task_type", "outcome"],
)

AGENT_SESSION_DURATION = Histogram(
    "agent_session_duration_seconds",
    "Wall-clock duration of a Claude Code agentic session",
    buckets=_SESSION_DURATION_BUCKETS,
)

AGENT_CYCLE_TIME = Histogram(
    "agent_cycle_time_seconds",
    "Lead time between pipeline stages (e.g. spec creation to first green CI)",
    ["stage"],  # stage: spec_to_green_ci | commit_to_deploy | pr_open_to_merge
    buckets=_CYCLE_TIME_BUCKETS,
)

SECURITY_FINDING_COUNTER = Counter(
    "security_finding_total",
    "Security findings from CI gates, by tool and severity",
    ["tool", "severity", "status"],  # status: open|resolved
)


# ── Helper functions (new metrics) ───────────────────────────────────────────


def record_subtask(
    agent_role: str,
    harness_mode: str,
    duration_seconds: float,
    error_type: str | None = None,
) -> None:
    AGENT_SUBTASK_DURATION.labels(agent_role, harness_mode).observe(duration_seconds)
    if error_type:
        AGENT_SUBTASK_ERROR_COUNTER.labels(agent_role, error_type).inc()


def record_session_task(
    task_type: str,
    outcome: str,
) -> None:
    AGENT_SESSION_TASKS_COUNTER.labels(task_type, outcome).inc()


def record_cycle_time(stage: str, duration_seconds: float) -> None:
    AGENT_CYCLE_TIME.labels(stage).observe(duration_seconds)


# ── Tool registry metrics (Issue #16) ────────────────────────────────────────
# Spec: specs/ai/tool-registry.md §6 | ADR: ADR-0039

AGENT_TOOL_INVOCATIONS = Counter(
    "agent_tool_invocations_total",
    "Tool invocations by the agent, by tool name, risk level, and outcome",
    ["tool_name", "risk_level", "outcome"],
)


# ── Learn-stage metrics (Issue #15) ──────────────────────────────────────────
# Spec: specs/ai/learn-stage.md | ADR: ADR-0038

AGENT_LEARN_PRECEDENTS_INJECTED = Counter(
    "agent_learn_precedents_injected_total",
    "Precedents injected into the Reason-stage LLM context from the Learn stage",
    ["action_type", "outcome_influenced"],
)

# ── Behavioral monitoring metrics (BM1/BM2 — ADR-0049) ───────────────────────
# Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 3

AGENT_BEHAVIORAL_ANOMALY_COUNTER = Counter(
    "agent_behavioral_anomaly_total",
    "Agent proposed an action outside its historical behavioral envelope "
    "(possible drift or injection)",
    ["task_type", "action_type"],
)

AGENT_POLICY_DECISION_COUNTER = Counter(
    "agent_policy_decision_total",
    "Runtime policy gateway decisions by policy name and decision",
    ["policy_name", "decision"],  # decision: ALLOW | REQUIRE_HITL | BLOCK
)

# ── Groundedness SLI metrics (Issue #270 — ADR-0080) ─────────────────────────
# Spec: docs/ai/eval-scorecard.md · docs/ai/ai-observability-naming.md
# Groundedness is a separate safety SLI scored by tests/model_contract/test_groundedness.py,
# NOT a 5th EvaluatorScore dimension. It makes CLAUDE.md §3.6 (grounding / non-fabrication)
# measurable: the score is the share of an answer's claims supported by provided context, and a
# flag fires when an unsupported (hallucinated) claim is detected.

AGENT_GROUNDEDNESS_SCORE = Gauge(
    "agent_groundedness_score",
    "Latest groundedness score (0.0-1.0): share of an answer's claims supported by context",
    ["agent_id", "sprint_id"],
)

AGENT_HALLUCINATION_FLAGGED_COUNTER = Counter(
    "agent_hallucination_flagged_total",
    "Times an answer was flagged as containing an unsupported (hallucinated) claim",
    ["agent_id", "sprint_id"],
)


def record_groundedness(
    score: float,
    flagged: bool,
    agent_id: str = "unknown",
    sprint_id: str = "unknown",
) -> None:
    """Record a groundedness SLI sample.

    Sets the groundedness score gauge (0.0-1.0) and increments the hallucination
    counter when the answer was flagged as containing an unsupported claim.
    """
    AGENT_GROUNDEDNESS_SCORE.labels(agent_id, sprint_id).set(score)
    if flagged:
        AGENT_HALLUCINATION_FLAGGED_COUNTER.labels(agent_id, sprint_id).inc()
