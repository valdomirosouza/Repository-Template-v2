"""Unit tests for src/shared/config.py — production secret validation.

Spec: specs/system/architecture.md (Technology Stack)
ADR:  ADR-0008 (Secrets Management)
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.shared.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]


class TestProductionSecretValidation:
    def test_placeholder_llm_api_key_rejected_in_production(self):
        # The LLM key is only mandatory in production when AI agents are enabled (ADR-0059).
        with pytest.raises(ValidationError, match="LLM_API_KEY"):
            Settings(
                app_env="production",
                ai_agents_enabled=True,
                llm_api_key="placeholder-set-in-env",
                anthropic_api_key="",
                secret_key="super-secret-value-abc123-long-enough",
                database_url="postgresql+asyncpg://appuser:real-db-pass@prod-db:5432/appdb",
                redis_url="rediss://:real-redis-pass@prod-redis:6379/0",
                db_encryption_key="a" * 64,
                redis_tls_enabled=True,
            )

    def test_placeholder_llm_api_key_allowed_when_ai_disabled(self):
        # With AI agents disabled, a placeholder LLM key must NOT block production startup.
        s = Settings(
            app_env="production",
            ai_agents_enabled=False,
            llm_api_key="placeholder-set-in-env",
            secret_key="super-secret-value-abc123-long-enough",
            database_url="postgresql+asyncpg://appuser:real-db-pass@prod-db:5432/appdb",
            redis_url="rediss://:real-redis-pass@prod-redis:6379/0",
            db_encryption_key="a" * 64,
            redis_tls_enabled=True,
        )
        assert s.ai_agents_enabled is False

    def test_placeholder_secret_key_rejected_in_production(self):
        with pytest.raises(ValidationError, match="SECRET_KEY"):
            Settings(
                app_env="production",
                llm_api_key="sk-real-key-xyz",
                secret_key="placeholder-set-in-env",
            )

    def test_both_placeholders_rejected_in_production(self):
        with pytest.raises(ValidationError):
            Settings(
                app_env="production",
                llm_api_key="placeholder-set-in-env",
                secret_key="placeholder-set-in-env",
            )

    def test_real_secrets_accepted_in_production(self):
        s = Settings(
            app_env="production",
            llm_api_key="sk-ant-real-key-xyz",
            secret_key="super-secret-value-abc123-long-enough",
            database_url="postgresql+asyncpg://appuser:real-db-pass@prod-db:5432/appdb",
            redis_url="rediss://:real-redis-pass@prod-redis:6379/0",  # rediss:// (ADR-0019)
            db_encryption_key="a" * 64,  # valid 32-byte hex key (ADR-0018)
            redis_tls_enabled=True,  # required in production (ADR-0019)
        )
        assert s.app_env == "production"

    def test_placeholder_accepted_in_development(self):
        s = Settings(
            app_env="development",
            llm_api_key="placeholder-set-in-env",
            secret_key="placeholder-set-in-env",
        )
        assert s.app_env == "development"

    def test_placeholder_accepted_in_staging(self):
        s = Settings(
            app_env="staging",
            llm_api_key="placeholder-set-in-env",
            secret_key="placeholder-set-in-env",
        )
        assert s.app_env == "staging"

    def test_case_insensitive_placeholder_detection(self):
        with pytest.raises(ValidationError, match="LLM_API_KEY"):
            Settings(
                app_env="production",
                ai_agents_enabled=True,
                llm_api_key="PLACEHOLDER-SET-IN-ENV",
                anthropic_api_key="",
                secret_key="super-secret-value-abc123-long-enough",
                database_url="postgresql+asyncpg://appuser:real-db-pass@prod-db:5432/appdb",
                redis_url="rediss://:real-redis-pass@prod-redis:6379/0",
                db_encryption_key="a" * 64,
                redis_tls_enabled=True,
            )

    def test_placeholder_database_url_rejected_in_production(self):
        with pytest.raises(ValidationError, match="DATABASE_URL"):
            Settings(
                app_env="production",
                llm_api_key="sk-ant-real-key-xyz",
                secret_key="super-secret-value-abc123-long-enough",
                database_url="postgresql+asyncpg://appuser:placeholder-set-in-env@localhost:5432/appdb",
                redis_url="redis://:real-redis-pass@prod-redis:6379/0",
            )

    def test_placeholder_redis_url_rejected_in_production(self):
        with pytest.raises(ValidationError, match="REDIS_URL"):
            Settings(
                app_env="production",
                llm_api_key="sk-ant-real-key-xyz",
                secret_key="super-secret-value-abc123-long-enough",
                database_url="postgresql+asyncpg://appuser:real-db-pass@prod-db:5432/appdb",
                redis_url="redis://:placeholder-set-in-env@prod-redis:6379/0",
            )

    def test_hs256_short_secret_key_rejected_in_production(self):
        with pytest.raises(ValidationError, match="SECRET_KEY must be at least 32 characters"):
            Settings(
                app_env="production",
                llm_api_key="sk-ant-real-key-xyz",
                secret_key="tooshort",
                database_url="postgresql+asyncpg://appuser:real-db-pass@prod-db:5432/appdb",
                redis_url="redis://:real-redis-pass@prod-redis:6379/0",
            )


class TestEnvCompatibility:
    """`allowed_origins` accepts comma OR JSON; unknown env keys are ignored.

    Regression for the .env/.env.example ↔ Settings mismatch: `.env.example` documents a
    comma-separated `allowed_origins` and ships infra/frontend keys (POSTGRES_*, NEXT_PUBLIC_*,
    OTEL_*, JOB_*, …) that previously crashed `Settings()` on load (allowed_origins JSON-decode
    error, then extra_forbidden).
    """

    def test_allowed_origins_comma_separated(self):
        s = Settings(_env_file=None, allowed_origins="http://a.com, http://b.com")
        assert s.allowed_origins == ["http://a.com", "http://b.com"]

    def test_allowed_origins_json_list(self):
        s = Settings(_env_file=None, allowed_origins='["http://x.com","http://y.com"]')
        assert s.allowed_origins == ["http://x.com", "http://y.com"]

    def test_allowed_origins_empty_string_is_empty_list(self):
        assert Settings(_env_file=None, allowed_origins="").allowed_origins == []

    def test_allowed_origins_default_and_list_passthrough(self):
        assert Settings(_env_file=None).allowed_origins == ["http://localhost:3000"]
        assert Settings(_env_file=None, allowed_origins=["http://z.com"]).allowed_origins == [
            "http://z.com"
        ]

    def test_unknown_env_keys_are_ignored(self):
        # extra="ignore": keys that aren't Settings fields (infra/frontend/test vars in .env.example)
        # must not raise and must not become attributes.
        s = Settings(
            _env_file=None,
            postgres_password="x",
            next_public_api_base_url="y",
            job_batch_size="500",
        )
        assert not hasattr(s, "postgres_password")

    def test_env_example_is_loadable(self):
        # The repo's own .env.example must load via Settings (it ships comma-separated
        # allowed_origins + infra/frontend keys that previously crashed loading).
        s = Settings(_env_file=str(_REPO_ROOT / ".env.example"))
        assert isinstance(s.allowed_origins, list)
        assert s.allowed_origins  # non-empty
