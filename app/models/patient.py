from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LabRefRange(BaseModel):
    low: float
    high: float


class LabResult(BaseModel):
    lab_id: str = Field(description="Stable identifier within the input payload.")
    code: str = Field(description="Synthetic lab code, e.g. 'LDL_C'.")
    name: str
    value: float
    unit: str
    ref_range: LabRefRange
    collected_at: datetime


class Medication(BaseModel):
    name: str
    dose: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ImagingSummary(BaseModel):
    modality: str
    performed_at: date
    summary: str


class HistoryItem(BaseModel):
    occurred_at: date
    summary: str


class GenomicVariant(BaseModel):
    variant_id: str = Field(description="Stable identifier within the input payload.")
    gene: str = Field(description="Synthetic gene symbol, e.g. 'APOE'.")
    variant: str = Field(description="Synthetic variant string, e.g. 'rs1234 A>G'.")
    zygosity: Literal["het", "hom", "unknown"] = "unknown"
    significance: Literal["benign", "unknown", "risk_marker"] = Field(
        default="unknown",
        description="Synthetic-only annotation label. This is not clinical interpretation.",
    )
    note: str | None = Field(
        default=None, description="Optional synthetic note. Must not imply medical advice."
    )


class BiomarkerPoint(BaseModel):
    measured_at: datetime
    value: float


class BiomarkerSeries(BaseModel):
    series_id: str = Field(description="Stable identifier within the input payload.")
    code: str = Field(description="Synthetic biomarker code, e.g. 'HS_CRP'.")
    name: str
    unit: str
    ref_range: LabRefRange
    points: list[BiomarkerPoint] = Field(default_factory=list)


class SyntheticPatientPayload(BaseModel):
    schema_version: Literal["v1"] = "v1"
    case_id: str = Field(description="Synthetic dataset identifier.")
    patient_id: str = Field(description="Synthetic patient identifier (not real).")
    generated_at: datetime

    demographics: dict[str, str] = Field(
        description="Synthetic demographics. Keep deliberately coarse.", default_factory=dict
    )

    labs: list[LabResult] = Field(default_factory=list)
    genomics: list[GenomicVariant] = Field(default_factory=list)
    biomarker_series: list[BiomarkerSeries] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    imaging: list[ImagingSummary] = Field(default_factory=list)
    history: list[HistoryItem] = Field(default_factory=list)

    # Used to deterministically simulate failure cases in the mock provider.
    scenario_tags: list[str] = Field(default_factory=list)


class NormalizedLab(BaseModel):
    lab_id: str
    code: str
    name: str
    value: float
    unit: str
    ref_range: LabRefRange
    collected_at: datetime
    interpretation: Literal["low", "normal", "high"]


class NormalizedBiomarkerPoint(BaseModel):
    measured_at: datetime
    value: float
    interpretation: Literal["low", "normal", "high"]


class NormalizedBiomarkerSeries(BaseModel):
    series_id: str
    code: str
    name: str
    unit: str
    ref_range: LabRefRange
    points: list[NormalizedBiomarkerPoint]
    trend: Literal["increasing", "decreasing", "stable"]
    latest_interpretation: Literal["low", "normal", "high"]


class NormalizedPatient(BaseModel):
    schema_version: Literal["v1"] = "v1"
    case_id: str
    patient_id: str
    generated_at: datetime
    demographics: dict[str, str]
    labs: list[NormalizedLab]
    genomics: list[GenomicVariant]
    biomarker_series: list[NormalizedBiomarkerSeries]
    medications: list[Medication]
    imaging: list[ImagingSummary]
    history: list[HistoryItem]
    scenario_tags: list[str]


class RiskSummary(BaseModel):
    cardiovascular: float = Field(default=0.1, ge=0.0, le=1.0)
    metabolic: float = Field(default=0.1, ge=0.0, le=1.0)
    overall: float = Field(default=0.1, ge=0.0, le=1.0)
