from __future__ import annotations

from datetime import UTC, datetime

from app.models.patient import LabRefRange, LabResult, SyntheticPatientPayload
from app.services.normalizer import fingerprint_dict, normalize_patient


def _payload() -> SyntheticPatientPayload:
    return SyntheticPatientPayload(
        case_id="case_x",
        patient_id="synthetic_001",
        generated_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        demographics={"age": "45", "sex": "F"},
        labs=[
            LabResult(
                lab_id="lab1",
                code="LDL_C",
                name="LDL Cholesterol",
                value=140.0,
                unit="mg/dL",
                ref_range=LabRefRange(low=0.0, high=100.0),
                collected_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            ),
            LabResult(
                lab_id="lab2",
                code="A1C",
                name="HbA1c",
                value=5.2,
                unit="%",
                ref_range=LabRefRange(low=4.0, high=5.6),
                collected_at=datetime(2026, 3, 1, 9, 5, tzinfo=UTC),
            ),
        ],
        genomics=[
            {
                "variant_id": "v2",
                "gene": "SYN2",
                "variant": "rs2 A>G",
                "zygosity": "het",
                "significance": "unknown",
            },
            {
                "variant_id": "v1",
                "gene": "SYN1",
                "variant": "rs1 C>T",
                "zygosity": "hom",
                "significance": "risk_marker",
            },
        ],
        biomarker_series=[
            {
                "series_id": "s1",
                "code": "HS_CRP",
                "name": "hs-CRP",
                "unit": "mg/L",
                "ref_range": {"low": 0.0, "high": 3.0},
                "points": [
                    {"measured_at": datetime(2026, 1, 1, 9, 0, tzinfo=UTC), "value": 1.0},
                    {"measured_at": datetime(2026, 3, 1, 9, 0, tzinfo=UTC), "value": 4.0},
                ],
            }
        ],
        scenario_tags=["b", "a"],
    )


def test_normalize_patient_interpretation_and_sorting() -> None:
    normalized = normalize_patient(_payload())
    assert normalized.labs[0].lab_id == "lab1"
    assert normalized.labs[0].interpretation == "high"
    assert normalized.labs[1].interpretation == "normal"
    assert normalized.scenario_tags == ["a", "b"]
    assert [g.variant_id for g in normalized.genomics] == ["v1", "v2"]
    assert normalized.biomarker_series[0].series_id == "s1"
    assert normalized.biomarker_series[0].trend == "increasing"
    assert normalized.biomarker_series[0].latest_interpretation == "high"


def test_fingerprint_dict_is_stable() -> None:
    a = fingerprint_dict({"b": 2, "a": 1})
    b = fingerprint_dict({"a": 1, "b": 2})
    assert a == b
