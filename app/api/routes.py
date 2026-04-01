from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import (
    ArtifactsResponse,
    EvaluationResponse,
    GenerateReportResponse,
    ReportResponse,
)
from app.models.patient import SyntheticPatientPayload

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    # Minimal readiness: repository initialized + artifacts dir configured.
    state = request.app.state
    _ = state.repo  # type: ignore[attr-defined]
    _ = state.orchestrator  # type: ignore[attr-defined]
    return {"status": "ready"}


@router.post("/v1/reports/generate", response_model=GenerateReportResponse)
async def generate_report(
    payload: SyntheticPatientPayload, request: Request
) -> GenerateReportResponse:
    orchestrator = request.app.state.orchestrator  # type: ignore[attr-defined]
    final, evaluation, artifacts = await orchestrator.generate(payload=payload)
    status = (
        "failed"
        if isinstance(final.rejection, dict) and final.rejection.get("code") == "WORKFLOW_TIMEOUT"
        else "completed"
    )
    return GenerateReportResponse(
        report_id=final.report_id,
        workflow_id=final.workflow_id,
        correlation_id=final.correlation_id,
        status=status,
        accepted=final.accepted,
        evaluation_overall=evaluation.scores.get("overall") if evaluation else None,
        artifacts=artifacts,
    )


@router.get("/v1/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, request: Request) -> ReportResponse:
    repo = request.app.state.repo  # type: ignore[attr-defined]
    stored = repo.get_report(report_id=report_id)
    if stored is None or stored.final_json is None:
        raise HTTPException(status_code=404, detail="report not found")
    return ReportResponse(report=stored.final_json)


@router.get("/v1/reports/{report_id}/evaluation", response_model=EvaluationResponse)
async def get_evaluation(report_id: str, request: Request) -> EvaluationResponse:
    repo = request.app.state.repo  # type: ignore[attr-defined]
    stored = repo.get_report(report_id=report_id)
    if stored is None or stored.evaluation_json is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    return EvaluationResponse(evaluation=stored.evaluation_json)


@router.get("/v1/reports/{report_id}/artifacts", response_model=ArtifactsResponse)
async def get_artifacts(report_id: str, request: Request) -> ArtifactsResponse:
    repo = request.app.state.repo  # type: ignore[attr-defined]
    stored = repo.get_report(report_id=report_id)
    if stored is None or stored.artifacts_json is None:
        raise HTTPException(status_code=404, detail="artifacts not found")
    return ArtifactsResponse(artifacts=stored.artifacts_json)
