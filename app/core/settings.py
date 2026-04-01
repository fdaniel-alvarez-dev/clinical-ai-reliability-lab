from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")

    db_path: str = Field(default="./artifacts/reports.sqlite", alias="DB_PATH")
    artifacts_dir: str = Field(default="./artifacts", alias="ARTIFACTS_DIR")

    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_exporter_otlp_insecure: bool = Field(default=True, alias="OTEL_EXPORTER_OTLP_INSECURE")
    otel_service_name: str = Field(default="clinical-ai-reliability-lab", alias="OTEL_SERVICE_NAME")
