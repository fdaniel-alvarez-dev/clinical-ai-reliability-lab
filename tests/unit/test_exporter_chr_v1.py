from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.exporters.chr_v1_exporter import CHRv1Exporter
from app.models.evaluation import EvaluationResult
from app.models.patient import LabRefRange, LabResult, SyntheticPatientPayload
from app.models.report import ComprehensiveHealthReportDraft, ComprehensiveHealthReportFinal
from app.models.validation import ValidationDecision
from app.services.normalizer import normalize_patient


@pytest.mark.parametrize("accepted", [True, False])
def test_exporter_writes_expected_artifacts(tmp_path: Path, accepted: bool) -> None:
    payload = SyntheticPatientPayload(
        case_id="case_export",
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
    draft = ComprehensiveHealthReportDraft(
        generated_at=payload.generated_at,
        executive_summary="Synthetic summary.",
        findings=[],
        recommendations=[],
        input_fingerprint="in_fp",
        draft_fingerprint="dr_fp",
    )
    final = ComprehensiveHealthReportFinal(
        report_id="rpt_x",
        workflow_id="wf_x",
        correlation_id="corr_x",
        accepted=accepted,
        decision_at=datetime(2026, 4, 1, 12, 1, tzinfo=UTC),
        draft=draft if accepted else None,
        rejection=None if accepted else {"issues": []},
    )
    decision = ValidationDecision(accepted=accepted, decided_at=final.decision_at, issues=[])
    evaluation = EvaluationResult(evaluated_at=final.decision_at, scores={"overall": 1.0})

    run_dir = tmp_path / "rpt_x"
    index = CHRv1Exporter().export(
        artifacts_dir=run_dir,
        normalized=normalized,
        final=final,
        draft=draft,
        validation=decision,
        evaluation=evaluation,
    )

    assert (run_dir / "normalized_input.json").exists()
    assert (run_dir / "validation_decision.json").exists()
    assert (run_dir / "evaluation.json").exists()
    assert (run_dir / "final.json").exists()
    assert (run_dir / "artifacts_index.json").exists()
    assert "normalized_input.json" in index

    if accepted:
        assert (run_dir / "report.md").exists()
        assert (run_dir / "report.pdf").exists()
    else:
        assert (run_dir / "rejection.md").exists()
