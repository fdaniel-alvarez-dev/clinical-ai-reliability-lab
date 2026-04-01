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


class SyntheticPatientPayload(BaseModel):
    schema_version: Literal["v1"] = "v1"
    case_id: str = Field(description="Synthetic dataset identifier.")
    patient_id: str = Field(description="Synthetic patient identifier (not real).")
    generated_at: datetime

    demographics: dict[str, str] = Field(
        description="Synthetic demographics. Keep deliberately coarse.", default_factory=dict
    )

    labs: list[LabResult] = Field(default_factory=list)
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


class NormalizedPatient(BaseModel):
    schema_version: Literal["v1"] = "v1"
    case_id: str
    patient_id: str
    generated_at: datetime
    demographics: dict[str, str]
    labs: list[NormalizedLab]
    medications: list[Medication]
    imaging: list[ImagingSummary]
    history: list[HistoryItem]
    scenario_tags: list[str]


class RiskSummary(BaseModel):
    cardiovascular: float = Field(default=0.1, ge=0.0, le=1.0)
    metabolic: float = Field(default=0.1, ge=0.0, le=1.0)
    overall: float = Field(default=0.1, ge=0.0, le=1.0)
