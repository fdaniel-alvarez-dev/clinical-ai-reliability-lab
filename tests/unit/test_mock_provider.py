from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.providers.mock import MockProvider
from app.models.patient import LabRefRange, LabResult, SyntheticPatientPayload
from app.services.normalizer import normalize_patient
from app.workflows.biomarker_graph import build_biomarker_graph


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic_for_same_input() -> None:
    payload = SyntheticPatientPayload(
        case_id="case_repeat",
        patient_id="synthetic_001",
        generated_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        labs=[
            LabResult(
                lab_id="lab1",
                code="LDL_C",
                name="LDL Cholesterol",
                value=140.0,
                unit="mg/dL",
                ref_range=LabRefRange(low=0.0, high=100.0),
                collected_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            )
        ],
    )
    normalized = normalize_patient(payload)
    _graph, concerns = build_biomarker_graph(normalized=normalized)
    provider = MockProvider()

    a = await provider.generate_chr_draft(
        normalized=normalized, workflow="chr_v1", concerns=concerns
    )
    b = await provider.generate_chr_draft(
        normalized=normalized, workflow="chr_v1", concerns=concerns
    )
    assert a == b
