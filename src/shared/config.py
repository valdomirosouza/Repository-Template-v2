"""Application configuration loaded from environment variables via Pydantic Settings.

Spec: specs/system/architecture.md (Technology Stack)
ADR:  ADR-0002 (Technology Stack Selection), ADR-0008 (Secrets Management)
"""

from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode

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
    # TLS settings for Redis connections (ADR-0019).
    # In production: set redis_tls_enabled=True and use rediss:// URL scheme.
    redis_tls_enabled: bool = False
    redis_tls_ca_cert: str = ""  # path to CA cert file; empty = use system CAs
    # Redis High Availability — Sentinel mode (see docs/sre/runbooks/redis-ha.md).
    # When redis_sentinel_enabled=True, redis_url is used as a fallback only;
    # the Sentinel cluster manages primary discovery automatically.
    redis_sentinel_enabled: bool = False
    redis_sentinel_master_name: str = "mymaster"
    redis_sentinel_hosts: str = ""  # comma-separated "host:port" pairs

    # ── Kafka ─────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "template-consumer-group"
    kafka_schema_registry_url: str = "http://localhost:8081"
    kafka_dlq_topic: str = "domain.request.dlq"  # topic for unrecoverable messages (REM-012)
    kafka_consumer_max_retries: int = 3  # attempts before routing to DLQ (REM-012)
    kafka_consumer_retry_backoff_seconds: float = 1.0  # base delay; doubles each attempt

    # ── LLM / AI ──────────────────────────────────────────────────────────────
    # AI agents are OPT-IN. When disabled (default), no LLM key is required and the
    # app runs the full non-AI platform cleanly (Reusability Uplift, ADR-0059).
    ai_agents_enabled: bool = False
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    # Canonical LLM key. ANTHROPIC_API_KEY is a backward-compat alias used when this
    # is unset/placeholder (resolved in resolve_llm_api_key below).
    llm_api_key: str = "placeholder-set-in-env"
    anthropic_api_key: str = ""
    llm_max_tokens: int = 4096
    llm_token_budget_per_request: int = 2000
    hitl_approval_timeout_seconds: int = 3600
    hitl_risk_threshold: float = 0.4  # MEDIUM/HIGH boundary per specs/ai/hitl-hotl.md
    hotl_override_window_seconds: int = 300  # 5-min override window per specs/ai/hitl-hotl.md
    hotl_notification_slo_seconds: int = 60  # notify reviewer within 60s of HOTL execution
    hitl_max_pending_requests: int = 500  # hard cap on in-memory HITL request store
    hitl_redis_key_prefix: str = "hitl"
    hitl_redis_ttl_grace_hours: int = 24  # TTL extension beyond expires_at for active keys
    hitl_expired_ttl_days: int = 7  # retention period for archived (expired) HITL requests
    request_redis_key_prefix: str = "request"
    request_result_ttl_hours: int = 24
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
    harness_patch_proposal_threshold: int = (
        2  # consecutive failures before PatchProposal (0=disabled)
    )

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
    # When True, prompt/response content is attached as span events on llm.inference spans.
    # MUST remain False in production — Collector strips these events before Jaeger export.
    otel_capture_prompts: bool = False

    # ── Feature flags ─────────────────────────────────────────────────────────
    feature_flag_provider: str = "local"
    feature_flag_sdk_key: str = ""
    autonomous_mode_enabled: bool = False  # fallback for legacy is_autonomous_mode_enabled()

    # Granular autonomy thresholds (SPEC-autonomous-mode-levels)
    autonomy_low_risk_threshold: float = 0.3  # risk_score below this → eligible for LOW_RISK
    autonomy_medium_risk_threshold: float = 0.7  # risk_score at or below → eligible for MEDIUM_RISK
    # Comma-separated lists configurable via env vars
    autonomy_read_only_action_types: str = (
        "read_file,search_code,list_files,get_status,read_spec,read_adr"
    )
    autonomy_test_action_types: str = "generate_test,run_test,check_coverage,lint_check"

    # ── Concurrency ───────────────────────────────────────────────────────────
    max_concurrent_agents: int = 20  # asyncio.Semaphore cap on simultaneous agent coroutines

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "placeholder-set-in-env"
    # HS256 is symmetric and suitable for single-service deployments.
    # For multi-service or public-key verification use RS256 or ES256.
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 3600
    # Role claim required to submit HITL approval decisions (REM-001, ADR-0011).
    hitl_operator_role: str = "hitl-operator"
    # NoDecode: take the raw env string (skip pydantic-settings' default JSON decoding) so the
    # comma-separated form documented in .env.example is accepted, not only a JSON list.
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    rate_limit_requests_per_minute: int = 60

    # ── Request correlation (X-Request-ID, ADR-0076 / SPEC-API-001) ───────────
    # Header name carrying the per-request correlation id. Accepted inbound (validated) and echoed
    # on every response; also included as `request_id` in the structured error envelope.
    request_id_header: str = "X-Request-ID"
    request_id_max_length: int = 128  # printable-ASCII tokens longer than this are replaced

    # ── Pagination (list endpoints, ADR-0078 / SPEC-API-003) ──────────────────
    pagination_max_limit: int = 200  # hard cap on a page size, regardless of requested limit

    # ── Idempotency (Idempotency-Key, ADR-0077 / SPEC-API-002) ────────────────
    idempotency_redis_key_prefix: str = "idempotency"
    idempotency_ttl_hours: int = 24  # how long a key de-dups a submission (aligns with result TTL)
    # Salt mixed into the request fingerprint so stored hashes aren't a portable body identifier.
    idempotency_fingerprint_salt: str = "template-idempotency-v1"

    # Outbound SSRF allow-list (OWASP A10). Host(s) that server-side outbound requests may target,
    # validated by src/shared/url_allowlist.py. Empty (default) = no host restriction, but
    # cloud-metadata / link-local endpoints and non-http(s) schemes are blocked regardless.
    # Entries match a host exactly or as a dot-suffix (e.g. ".internal.example.com").
    outbound_url_allowlist: Annotated[list[str], NoDecode] = []

    # ── Database Encryption at Rest (ADR-0018) ────────────────────────────────
    # 64 hex characters = 32 bytes = AES-256 key.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    # In production this must come from Vault (ADR-0008); never commit a real key.
    db_encryption_key: str = "placeholder-set-in-env"
    db_encryption_enabled: bool = True  # set False only in local dev without Vault

    # ── Privacy ───────────────────────────────────────────────────────────────
    pii_masking_enabled: bool = True
    pii_audit_log_enabled: bool = True
    data_retention_days: int = 30

    # ── Feedback loop ─────────────────────────────────────────────────────────
    feedback_loop_interval_seconds: int = 300
    feedback_rejection_threshold: float = 0.30  # rejection rate above this triggers bias +0.1
    feedback_approval_threshold: float = (
        0.80  # sustained approval rate below this prevents bias reduction
    )
    feedback_min_samples: int = 10  # minimum decisions before any adjustment is made
    feedback_bias_step_up: float = 0.10  # amount added to bias on high rejection
    feedback_bias_step_down: float = 0.05  # amount subtracted from bias on sustained approval
    feedback_bias_max: float = 0.50  # hard cap on positive bias
    feedback_prometheus_url: str = "http://localhost:9090"

    # ── Sandbox execution ─────────────────────────────────────────────────────
    sandbox_docker_image: str = "python:3.13-slim"
    sandbox_exec_timeout_seconds: float = 30.0
    sandbox_cpu_limit: str = "1.0"
    sandbox_memory_limit: str = "512m"
    sandbox_stdout_max_bytes: int = 65_536  # 64 KB
    sandbox_stderr_max_bytes: int = 16_384  # 16 KB

    # ── FinOps ────────────────────────────────────────────────────────────────
    llm_monthly_token_budget: int = 1_000_000
    cost_alert_threshold_usd: float = 100.0

    @field_validator("allowed_origins", "outbound_url_allowlist", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, v: object) -> object:
        """Accept a comma-separated string (as documented in .env.example) or a JSON list.

        Already-list values (defaults, programmatic construction) pass through unchanged.
        """
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):  # JSON list form, e.g. '["http://a","http://b"]'
                import json

                return json.loads(s)
            return [origin.strip() for origin in s.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def resolve_llm_api_key(self) -> "Settings":
        """Canonicalise the LLM key and gate it on AI_AGENTS_ENABLED.

        ANTHROPIC_API_KEY is a backward-compat alias: when LLM_API_KEY is
        unset/placeholder but ANTHROPIC_API_KEY is set, adopt the latter. The LLM
        key is only *required* when AI agents are enabled — non-AI adopters run
        cleanly with no key (Reusability Uplift, ADR-0059).
        """
        if self.anthropic_api_key and (
            not self.llm_api_key or "placeholder" in self.llm_api_key.lower()
        ):
            self.llm_api_key = self.anthropic_api_key
        if self.ai_agents_enabled and (
            not self.llm_api_key or "placeholder" in self.llm_api_key.lower()
        ):
            raise ValueError(
                "AI_AGENTS_ENABLED=true but no LLM API key is configured. "
                "Set LLM_API_KEY (or the ANTHROPIC_API_KEY alias) in the environment, "
                "or set AI_AGENTS_ENABLED=false to run without AI agents."
            )
        return self

    @model_validator(mode="after")
    def reject_placeholder_secrets(self) -> "Settings":
        if self.app_env == "production":
            checks = {
                "SECRET_KEY": self.secret_key,
                "DATABASE_URL": self.database_url,
                "REDIS_URL": self.redis_url,
            }
            # The LLM key is only mandatory in production when AI agents are enabled.
            if self.ai_agents_enabled:
                checks["LLM_API_KEY"] = self.llm_api_key
            for name, value in checks.items():
                if "placeholder" in value.lower():
                    raise ValueError(f"{name} must be set via environment variable in production")
            if self.jwt_algorithm == "HS256" and len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters when using HS256. "
                    'Generate with: python -c "import secrets; print(secrets.token_hex(32))". '
                    "Consider RS256 with asymmetric keys for stronger security."
                )
            if self.db_encryption_enabled and "placeholder" in self.db_encryption_key.lower():
                raise ValueError(
                    "DB_ENCRYPTION_KEY must be set via environment variable in production. "
                    'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            if not self.redis_tls_enabled and not self.redis_url.startswith("rediss://"):
                raise ValueError(
                    "Redis TLS is required in production. "
                    "Set REDIS_TLS_ENABLED=true and use a rediss:// URL (ADR-0019)."
                )
        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        # Ignore env/.env keys that aren't Settings fields. .env.example legitimately ships
        # infra/frontend/test keys (POSTGRES_*, REDIS_PASSWORD, NEXT_PUBLIC_*, OTEL_*, JOB_*, …)
        # consumed by docker-compose / the frontend / the OTel SDK — not by this model. Without
        # this, loading a .env copied from .env.example raises extra_forbidden.
        "extra": "ignore",
    }


settings = Settings()
