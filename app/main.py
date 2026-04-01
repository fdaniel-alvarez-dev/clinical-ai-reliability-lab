from __future__ import annotations

from fastapi import FastAPI

from app.adapters.providers.factory import provider_from_settings
from app.api.routes import router as v1_router
from app.core.settings import Settings
from app.evaluators.chr_v1_evaluator import CHRv1Evaluator
from app.exporters.chr_v1_exporter import CHRv1Exporter
from app.observability.correlation import CorrelationIdMiddleware
from app.observability.logging import configure_logging
from app.observability.otel import configure_otel, instrument_fastapi
from app.services.job_runner import JobRunner, JobRunnerConfig
from app.services.report_orchestrator import ReportOrchestrator
from app.storage.artifact_store_factory import artifact_store_from_settings
from app.storage.sqlite_repo import SqliteReportRepository
from app.ui.routes import router as ui_router
from app.validators.chr_v1_validator import CHRv1DeterministicValidator


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(log_level=settings.log_level)
    configure_otel(settings=settings)

    app = FastAPI(
        title="clinical-ai-reliability-lab",
        version="0.1.0",
        description=(
            "A reliability-first clinical-like AI workflow demo. "
            "Synthetic data only. Not medical advice."
        ),
    )
    app.add_middleware(CorrelationIdMiddleware)

    repo = SqliteReportRepository(db_path=settings.db_path)
    artifact_store = artifact_store_from_settings(settings=settings)
    provider = provider_from_settings(settings)
    validator = CHRv1DeterministicValidator()
    evaluator = CHRv1Evaluator()
    exporter = CHRv1Exporter()
    orchestrator = ReportOrchestrator(
        provider=provider,
        validator=validator,
        evaluator=evaluator,
        exporter=exporter,
        repo=repo,
        artifact_store=artifact_store,
        provider_max_attempts=settings.provider_max_attempts,
        provider_retry_base_s=settings.provider_retry_base_s,
        provider_retry_max_s=settings.provider_retry_max_s,
    )

    job_runner = JobRunner(
        repo=repo,
        orchestrator=orchestrator,
        config=JobRunnerConfig(
            max_attempts=settings.job_max_attempts,
            retry_base_s=settings.provider_retry_base_s,
            retry_max_s=settings.provider_retry_max_s,
        ),
    )

    app.state.settings = settings
    app.state.repo = repo
    app.state.orchestrator = orchestrator
    app.state.job_runner = job_runner

    @app.on_event("startup")
    async def _startup() -> None:
        job_runner.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await job_runner.stop()

    app.include_router(v1_router)
    app.include_router(ui_router)
    instrument_fastapi(app)
    return app


app = create_app()
