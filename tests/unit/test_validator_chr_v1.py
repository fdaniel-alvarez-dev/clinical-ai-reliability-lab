from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.providers.mock import MockProvider
from app.models.patient import (
    BiomarkerPoint,
    BiomarkerSeries,
    GenomicVariant,
    LabRefRange,
    LabResult,
    SyntheticPatientPayload,
)
from app.models.report import ComprehensiveHealthReportDraft
from app.services.normalizer import normalize_patient
from app.validators.chr_v1_validator import CHRv1DeterministicValidator


def _base_payload(*, tags: list[str] | None = None) -> SyntheticPatientPayload:
    return SyntheticPatientPayload(
        case_id="case_base",
        patient_id="synthetic_001",
        generated_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        labs=[
            LabResult(
                lab_id="lab_ldl",
                code="LDL_C",
                name="LDL Cholesterol",
                value=140.0,
                unit="mg/dL",
                ref_range=LabRefRange(low=0.0, high=100.0),
                collected_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            ),
            LabResult(
                lab_id="lab_a1c",
                code="A1C",
                name="HbA1c",
                value=5.2,
                unit="%",
                ref_range=LabRefRange(low=4.0, high=5.6),
                collected_at=datetime(2026, 3, 1, 9, 5, tzinfo=UTC),
            ),
        ],
        scenario_tags=tags or [],
    )


@pytest.mark.asyncio
async def test_validator_accepts_stable_case() -> None:
    normalized = normalize_patient(_base_payload(tags=[]))
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is True
    assert decision.issues == []


@pytest.mark.asyncio
async def test_validator_rejects_hallucinated_evidence_ref() -> None:
    normalized = normalize_patient(_base_payload(tags=["hallucinated_claim_risk"]))
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is False
    assert any("not found in labs" in i.message for i in decision.issues)


@pytest.mark.asyncio
async def test_validator_rejects_contradictory_lab_claim() -> None:
    normalized = normalize_patient(_base_payload(tags=["contradictory_lab_history"]))
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is False
    assert any(i.code == "VALIDATION_FAILED_CONTRADICTION" for i in decision.issues)


@pytest.mark.asyncio
async def test_validator_rejects_abnormal_omission() -> None:
    normalized = normalize_patient(_base_payload(tags=["omit_abnormal_biomarker"]))
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is False
    assert any(i.code == "VALIDATION_FAILED_CRITICAL_OMISSION" for i in decision.issues)


@pytest.mark.asyncio
async def test_validator_rejects_prescriptive_recommendation_and_missing_evidence() -> None:
    normalized = normalize_patient(_base_payload(tags=["missing_critical_context"]))
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is False
    assert any(
        i.code in {"INSUFFICIENT_EVIDENCE", "VALIDATION_FAILED_UNSUPPORTED_CLAIM"}
        for i in decision.issues
    )


@pytest.mark.asyncio
async def test_validator_rejects_genomic_risk_marker_omission() -> None:
    payload = _base_payload(tags=["omit_genomic_risk_marker"])
    payload.genomics = [
        GenomicVariant(
            variant_id="v_risk_1",
            gene="SYN_APOE",
            variant="rs9999 C>T",
            zygosity="het",
            significance="risk_marker",
        )
    ]
    normalized = normalize_patient(payload)
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is False
    assert any(i.code == "VALIDATION_FAILED_CRITICAL_OMISSION" for i in decision.issues)


@pytest.mark.asyncio
async def test_validator_rejects_contradictory_biomarker_trend() -> None:
    payload = _base_payload(tags=["contradictory_biomarker_trend"])
    payload.biomarker_series = [
        BiomarkerSeries(
            series_id="s1",
            code="HS_CRP",
            name="hs-CRP",
            unit="mg/L",
            ref_range=LabRefRange(low=0.0, high=3.0),
            points=[
                BiomarkerPoint(measured_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC), value=1.0),
                BiomarkerPoint(measured_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC), value=4.0),
            ],
        )
    ]
    normalized = normalize_patient(payload)
    draft_dict = await MockProvider().generate_chr_draft(normalized=normalized)
    draft = ComprehensiveHealthReportDraft.model_validate(draft_dict)
    decision = CHRv1DeterministicValidator().validate(normalized=normalized, draft=draft)
    assert decision.accepted is False
    assert any(i.code == "VALIDATION_FAILED_CONTRADICTION" for i in decision.issues)
