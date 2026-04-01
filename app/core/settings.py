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
    artifact_store: str = Field(default="local", alias="ARTIFACT_STORE")
    artifact_store_bucket: str | None = Field(default=None, alias="ARTIFACT_STORE_BUCKET")
    artifact_store_prefix: str = Field(default="clinical-ai-reliability-lab", alias="ARTIFACT_STORE_PREFIX")
    artifact_store_s3_endpoint_url: str | None = Field(default=None, alias="ARTIFACT_STORE_S3_ENDPOINT_URL")
    artifact_store_s3_region: str | None = Field(default=None, alias="ARTIFACT_STORE_S3_REGION")

    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_exporter_otlp_insecure: bool = Field(default=True, alias="OTEL_EXPORTER_OTLP_INSECURE")
    otel_service_name: str = Field(default="clinical-ai-reliability-lab", alias="OTEL_SERVICE_NAME")

    job_max_attempts: int = Field(default=2, alias="JOB_MAX_ATTEMPTS", ge=1, le=10)
    provider_max_attempts: int = Field(default=2, alias="PROVIDER_MAX_ATTEMPTS", ge=1, le=5)
    provider_retry_base_s: float = Field(default=0.2, alias="PROVIDER_RETRY_BASE_S", ge=0.0, le=5.0)
    provider_retry_max_s: float = Field(default=2.0, alias="PROVIDER_RETRY_MAX_S", ge=0.0, le=30.0)
