from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    kind: Literal[
        "lab",
        "medication",
        "imaging",
        "history",
        "genomic_variant",
        "biomarker_series",
    ]
    id: str = Field(description="Identifier within the normalized input (e.g., lab_id).")


class Finding(BaseModel):
    finding_id: str
    category: Literal["lab", "medication", "imaging", "history", "genomics", "biomarker"]
    title: str
    statement: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    severity: Literal["info", "mild", "moderate", "high"] = "info"


class Recommendation(BaseModel):
    rec_id: str
    title: str
    statement: str
    rationale: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    safety_note: str = Field(
        default="Educational demo only. Not medical advice.",
        description="Always include an explicit non-medical-advice safety note.",
    )


class ComprehensiveHealthReportDraft(BaseModel):
    schema_version: Literal["chr_v1"] = "chr_v1"
    generated_at: datetime

    # Human-readable content
    executive_summary: str
    findings: list[Finding]
    recommendations: list[Recommendation]

    # Deterministic traceability hooks
    input_fingerprint: str = Field(description="Hash of normalized input used for traceability.")
    draft_fingerprint: str = Field(description="Hash of draft payload for traceability.")


class ComprehensiveHealthReportFinal(BaseModel):
    schema_version: Literal["chr_v1"] = "chr_v1"
    report_id: str
    workflow_id: str
    correlation_id: str

    accepted: bool
    decision_at: datetime

    draft: ComprehensiveHealthReportDraft | None = None
    rejection: dict[str, object] | None = None
