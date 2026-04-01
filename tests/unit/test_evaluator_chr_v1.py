from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.providers.mock import MockProvider
from app.evaluators.chr_v1_evaluator import CHRv1Evaluator
from app.models.patient import LabRefRange, LabResult, SyntheticPatientPayload
from app.models.report import ComprehensiveHealthReportDraft
from app.services.normalizer import normalize_patient
from app.validators.chr_v1_validator import CHRv1DeterministicValidator


def _payload(*, tags: list[str]) -> SyntheticPatientPayload:
    return SyntheticPatientPayload(
        case_id="case_eval",
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
            )
        ],
        scenario_tags=tags,
    )


@pytest.mark.asyncio
async def test_evaluator_scores_accepted_higher_than_rejected() -> None:
    evaluator = CHRv1Evaluator()
    validator = CHRv1DeterministicValidator()
    provider = MockProvider()

    norm_ok = normalize_patient(_payload(tags=[]))
    draft_ok = ComprehensiveHealthReportDraft.model_validate(
        await provider.generate_chr_draft(normalized=norm_ok)
    )
    decision_ok = validator.validate(normalized=norm_ok, draft=draft_ok)
    eval_ok = evaluator.evaluate(normalized=norm_ok, draft=draft_ok, validation=decision_ok)

    norm_bad = normalize_patient(_payload(tags=["omit_abnormal_biomarker"]))
    draft_bad = ComprehensiveHealthReportDraft.model_validate(
        await provider.generate_chr_draft(normalized=norm_bad)
    )
    decision_bad = validator.validate(normalized=norm_bad, draft=draft_bad)
    eval_bad = evaluator.evaluate(normalized=norm_bad, draft=draft_bad, validation=decision_bad)

    assert decision_ok.accepted is True
    assert decision_bad.accepted is False
    assert eval_ok.scores["overall"] > eval_bad.scores["overall"]
    assert eval_ok.scores["overall"] <= 1.0
    assert eval_bad.scores["overall"] >= 0.0
