from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.api.schemas import (
    ArtifactsResponse,
    CreateJobResponse,
    EvaluationResponse,
    GenerateReportResponse,
    JobResponse,
    ReportResponse,
)
from app.core.ids import new_correlation_id, new_job_id, new_report_id, new_workflow_id
from app.models.job import JobStatus
from app.models.patient import SyntheticPatientPayload
from app.services.normalizer import fingerprint_dict, normalize_patient
from app.workflows.chr.factory import available_workflows, normalize_workflow_name

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
    _ = state.job_runner  # type: ignore[attr-defined]
    return {"status": "ready"}


@router.post("/v1/reports/generate", response_model=GenerateReportResponse)
async def generate_report(
    payload: SyntheticPatientPayload,
    request: Request,
    workflow: str = Query(default="chr_v1", description="chr_v1|easy_chr|sequential_chr|functional_chr"),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> GenerateReportResponse:
    try:
        _ = normalize_workflow_name(workflow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    orchestrator = request.app.state.orchestrator  # type: ignore[attr-defined]
    final, evaluation, artifacts = await orchestrator.generate(
        payload=payload, workflow=workflow, correlation_id=correlation_id
    )
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


@router.get("/v1/workflows")
async def list_workflows() -> dict[str, list[str]]:
    return {"workflows": available_workflows()}


@router.post("/v1/jobs", response_model=CreateJobResponse)
async def create_job(
    payload: SyntheticPatientPayload,
    request: Request,
    workflow: str = Query(default="chr_v1", description="chr_v1|easy_chr|sequential_chr|functional_chr"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> CreateJobResponse:
    try:
        _ = normalize_workflow_name(workflow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo = request.app.state.repo  # type: ignore[attr-defined]
    job_runner = request.app.state.job_runner  # type: ignore[attr-defined]
    settings = request.app.state.settings  # type: ignore[attr-defined]

    normalized = normalize_patient(payload)
    payload_fingerprint = fingerprint_dict(normalized.model_dump(mode="json"))

    if idempotency_key:
        existing = repo.find_job_by_idempotency(workflow=workflow, idempotency_key=idempotency_key)
        if existing is not None:
            if existing.payload_fingerprint != payload_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key reuse with a different payload_fingerprint.",
                )
            return CreateJobResponse(
                job_id=existing.job_id,
                report_id=existing.report_id,
                workflow_id=existing.workflow_id,
                correlation_id=existing.correlation_id,
                status=existing.status.value,
            )

    job_id = new_job_id()
    report_id = new_report_id()
    workflow_id = new_workflow_id()
    correlation_id = correlation_id or new_correlation_id()
    repo.create_job(
        job_id=job_id,
        workflow=workflow,
        idempotency_key=idempotency_key,
        payload_fingerprint=payload_fingerprint,
        payload_json=payload.model_dump(mode="json"),
        report_id=report_id,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        status=JobStatus.queued,
        max_attempts=settings.job_max_attempts,
    )
    job_runner.enqueue(job_id=job_id)
    return CreateJobResponse(
        job_id=job_id,
        report_id=report_id,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        status=JobStatus.queued.value,
    )


@router.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, request: Request) -> JobResponse:
    repo = request.app.state.repo  # type: ignore[attr-defined]
    job = repo.get_job(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(
        job={
            "job_id": job.job_id,
            "workflow": job.workflow,
            "status": job.status.value,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
            "last_error": job.last_error,
            "report_id": job.report_id,
            "workflow_id": job.workflow_id,
            "correlation_id": job.correlation_id,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
    )


@router.post("/v1/jobs/{job_id}/replay", response_model=CreateJobResponse)
async def replay_job(
    job_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> CreateJobResponse:
    repo = request.app.state.repo  # type: ignore[attr-defined]
    job_runner = request.app.state.job_runner  # type: ignore[attr-defined]
    settings = request.app.state.settings  # type: ignore[attr-defined]

    existing = repo.get_job(job_id=job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="job not found")

    if idempotency_key:
        found = repo.find_job_by_idempotency(workflow=existing.workflow, idempotency_key=idempotency_key)
        if found is not None:
            if found.payload_fingerprint != existing.payload_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key reuse with a different payload_fingerprint.",
                )
            return CreateJobResponse(
                job_id=found.job_id,
                report_id=found.report_id,
                workflow_id=found.workflow_id,
                correlation_id=found.correlation_id,
                status=found.status.value,
            )

    new_id = new_job_id()
    report_id = new_report_id()
    workflow_id = new_workflow_id()
    correlation_id = correlation_id or new_correlation_id()
    repo.create_job(
        job_id=new_id,
        workflow=existing.workflow,
        idempotency_key=idempotency_key,
        payload_fingerprint=existing.payload_fingerprint,
        payload_json=existing.payload_json,
        report_id=report_id,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        status=JobStatus.queued,
        max_attempts=settings.job_max_attempts,
    )
    job_runner.enqueue(job_id=new_id)
    return CreateJobResponse(
        job_id=new_id,
        report_id=report_id,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        status=JobStatus.queued.value,
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
