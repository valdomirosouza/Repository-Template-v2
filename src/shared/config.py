"""Application configuration loaded from environment variables via Pydantic Settings.

Spec: specs/system/architecture.md (Technology Stack)
ADR:  ADR-0002 (Technology Stack Selection), ADR-0008 (Secrets Management)
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_version_file = Path(__file__).parent.parent.parent / "version.txt"
_service_version_default: str = (
    _version_file.read_text(encoding="utf-8").strip() if _version_file.exists() else "0.0.0"
)


class Settings(BaseSettings):
    # ── App core ──────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"
    service_name: str = "template-service"
    service_version: str = _service_version_default

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://appuser:placeholder-set-in-env@localhost:5432/appdb"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://:placeholder-set-in-env@localhost:6379/0"
    redis_max_connections: int = 50

    # ── Kafka ─────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "template-consumer-group"
    kafka_schema_registry_url: str = "http://localhost:8081"

    # ── LLM / AI ──────────────────────────────────────────────────────────────
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    llm_api_key: str = "placeholder-set-in-env"
    llm_max_tokens: int = 4096
    llm_token_budget_per_request: int = 2000
    hitl_approval_timeout_seconds: int = 3600
    hitl_risk_threshold: float = 0.4  # MEDIUM/HIGH boundary per specs/ai/hitl-hotl.md
    hotl_override_window_seconds: int = 300  # 5-min override window per specs/ai/hitl-hotl.md
    hitl_max_pending_requests: int = 500  # hard cap on in-memory HITL request store
    hitl_redis_key_prefix: str = "hitl"
    hitl_redis_ttl_grace_hours: int = 24  # TTL extension beyond expires_at for active keys
    hitl_expired_ttl_days: int = 7  # retention period for archived (expired) HITL requests
    llm_call_timeout_seconds: float = 30.0  # asyncio.wait_for ceiling on LLM API calls
    redis_call_timeout_seconds: float = 5.0  # asyncio.wait_for ceiling on Redis pipeline calls
    shutdown_drain_seconds: int = 5  # grace period before pool teardown (LB deregister)
    llm_circuit_breaker_threshold: int = 5  # consecutive failures before circuit opens
    llm_circuit_breaker_reset_seconds: float = 60.0  # half-open probe interval after circuit opens
    llm_retry_max_attempts: int = 3  # max retry attempts on transient LLM errors

    # ── Harness ───────────────────────────────────────────────────────────────
    harness_mode: str = "solo"  # solo | simplified | full
    harness_context_reset_threshold: float = 0.85  # context utilisation → reset
    harness_max_iterations: int = 15  # max evaluator retries per sprint
    harness_evaluator_pass_threshold: float = 0.75  # min score per dimension to pass
    harness_planner_enabled: bool = True  # disable to skip Planner in full mode
    harness_evaluator_enabled: bool = True  # disable to skip Evaluator (debug only)
    harness_planner_hitl_review: bool = False  # opt-in: HITL review of ProductSpec
    harness_patch_proposal_threshold: int = 2  # consecutive failures before PatchProposal (0=disabled)

    # ── Agent Memory (ADR-0017) ───────────────────────────────────────────────
    memory_session_ttl_seconds: int = 86400  # 24 h Redis session TTL
    memory_vector_search_k: int = 5  # default top-k for similarity search
    memory_embedding_dim: int = 256  # embedding vector dimension (must match embedder)
    memory_docs_retention_days: int = 90  # vector doc retention (aligns with ADR-0013)

    # ── Observability ─────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "template-service"
    prometheus_port: int = 9090
    jaeger_agent_host: str = "localhost"

    # ── Feature flags ─────────────────────────────────────────────────────────
    feature_flag_provider: str = "local"
    feature_flag_sdk_key: str = ""
    autonomous_mode_enabled: bool = False  # fallback for legacy is_autonomous_mode_enabled()

    # Granular autonomy thresholds (SPEC-autonomous-mode-levels)
    autonomy_low_risk_threshold: float = 0.3    # risk_score below this → eligible for LOW_RISK
    autonomy_medium_risk_threshold: float = 0.7  # risk_score at or below → eligible for MEDIUM_RISK
    # Comma-separated lists configurable via env vars
    autonomy_read_only_action_types: str = "read_file,search_code,list_files,get_status,read_spec,read_adr"
    autonomy_test_action_types: str = "generate_test,run_test,check_coverage,lint_check"

    # ── Concurrency ───────────────────────────────────────────────────────────
    max_concurrent_agents: int = 20  # asyncio.Semaphore cap on simultaneous agent coroutines

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "placeholder-set-in-env"
    # HS256 is symmetric and suitable for single-service deployments.
    # For multi-service or public-key verification use RS256 or ES256.
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 3600
    allowed_origins: list[str] = ["http://localhost:3000"]
    rate_limit_requests_per_minute: int = 60

    # ── Privacy ───────────────────────────────────────────────────────────────
    pii_masking_enabled: bool = True
    pii_audit_log_enabled: bool = True
    data_retention_days: int = 30

    # ── FinOps ────────────────────────────────────────────────────────────────
    llm_monthly_token_budget: int = 1_000_000
    cost_alert_threshold_usd: float = 100.0

    @model_validator(mode="after")
    def reject_placeholder_secrets(self) -> "Settings":
        if self.app_env == "production":
            checks = {
                "LLM_API_KEY": self.llm_api_key,
                "SECRET_KEY": self.secret_key,
                "DATABASE_URL": self.database_url,
                "REDIS_URL": self.redis_url,
            }
            for name, value in checks.items():
                if "placeholder" in value.lower():
                    raise ValueError(f"{name} must be set via environment variable in production")
            if self.jwt_algorithm == "HS256" and len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters when using HS256. "
                    "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\". "
                    "Consider RS256 with asymmetric keys for stronger security."
                )
        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
