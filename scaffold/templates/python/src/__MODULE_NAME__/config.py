"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"
    service_name: str = "__SERVICE_NAME__"

    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
