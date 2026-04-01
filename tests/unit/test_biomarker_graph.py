from __future__ import annotations

from datetime import UTC, datetime

from app.models.patient import (
    BiomarkerPoint,
    BiomarkerSeries,
    LabRefRange,
    LabResult,
    SyntheticPatientPayload,
)
from app.services.normalizer import normalize_patient
from app.workflows.biomarker_graph import build_biomarker_graph


def test_biomarker_graph_builds_nodes_edges_and_concerns() -> None:
    payload = SyntheticPatientPayload(
        case_id="case_bg",
        patient_id="synthetic_bg_001",
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
        biomarker_series=[
            BiomarkerSeries(
                series_id="series_hs_crp",
                code="HS_CRP",
                name="hs-CRP",
                unit="mg/L",
                ref_range=LabRefRange(low=0.0, high=3.0),
                points=[
                    BiomarkerPoint(measured_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC), value=1.0),
                    BiomarkerPoint(measured_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC), value=4.0),
                ],
            )
        ],
    )
    normalized = normalize_patient(payload)
    graph, concerns = build_biomarker_graph(normalized=normalized)

    assert len(graph.nodes) >= 3  # lab + series + at least one domain
    assert any(n.kind == "domain" for n in graph.nodes)
    assert any(e.relation == "belongs_to" for e in graph.edges)
    assert any("Abnormal" in c.title for c in concerns)

