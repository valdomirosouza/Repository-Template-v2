"""Unit tests for src/shared/config.py — production secret validation.

Spec: specs/system/architecture.md (Technology Stack)
ADR:  ADR-0008 (Secrets Management)
"""

import pytest
from pydantic import ValidationError

from src.shared.config import Settings


class TestProductionSecretValidation:
    def test_placeholder_llm_api_key_rejected_in_production(self):
        with pytest.raises(ValidationError, match="LLM_API_KEY"):
            Settings(
                app_env="production",
                llm_api_key="placeholder-set-in-env",
                secret_key="real-secret-value-xyz",
            )

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
                llm_api_key="PLACEHOLDER-SET-IN-ENV",
                secret_key="real-secret",
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
