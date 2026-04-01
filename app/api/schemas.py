from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateReportResponse(BaseModel):
    report_id: str
    workflow_id: str
    correlation_id: str
    status: str = Field(description="completed|failed")
    accepted: bool
    evaluation_overall: float | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    report: dict[str, object]


class EvaluationResponse(BaseModel):
    evaluation: dict[str, object]


class ArtifactsResponse(BaseModel):
    artifacts: dict[str, str]
