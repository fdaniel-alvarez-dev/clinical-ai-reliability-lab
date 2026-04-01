from __future__ import annotations

from fastapi import FastAPI

from app.adapters.providers.factory import provider_from_settings
from app.api.routes import router as v1_router
from app.core.settings import Settings
from app.evaluators.chr_v1_evaluator import CHRv1Evaluator
from app.exporters.chr_v1_exporter import CHRv1Exporter
from app.observability.logging import configure_logging
from app.observability.otel import configure_otel, instrument_fastapi
from app.services.report_orchestrator import ReportOrchestrator
from app.storage.sqlite_repo import SqliteReportRepository
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

    repo = SqliteReportRepository(db_path=settings.db_path)
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
        artifacts_dir=settings.artifacts_dir,
    )

    app.state.settings = settings
    app.state.repo = repo
    app.state.orchestrator = orchestrator

    app.include_router(v1_router)
    instrument_fastapi(app)
    return app


app = create_app()
