from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from app.models.patient import (
    BiomarkerPoint,
    BiomarkerSeries,
    LabResult,
    NormalizedBiomarkerPoint,
    NormalizedBiomarkerSeries,
    NormalizedLab,
    NormalizedPatient,
    SyntheticPatientPayload,
)


def _interpret_lab(lab: LabResult) -> Literal["low", "normal", "high"]:
    if lab.value < lab.ref_range.low:
        return "low"
    if lab.value > lab.ref_range.high:
        return "high"
    return "normal"


def _interpret_biomarker_point(
    *, series: BiomarkerSeries, point: BiomarkerPoint
) -> Literal["low", "normal", "high"]:
    if point.value < series.ref_range.low:
        return "low"
    if point.value > series.ref_range.high:
        return "high"
    return "normal"


def _trend(*, first: float, last: float) -> Literal["increasing", "decreasing", "stable"]:
    if last > first:
        return "increasing"
    if last < first:
        return "decreasing"
    return "stable"


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def fingerprint_dict(payload: dict[str, Any]) -> str:
    stable = _stable_json(payload).encode("utf-8")
    return hashlib.sha256(stable).hexdigest()


def normalize_patient(payload: SyntheticPatientPayload) -> NormalizedPatient:
    normalized_labs = [
        NormalizedLab(
            lab_id=lab.lab_id,
            code=lab.code,
            name=lab.name,
            value=lab.value,
            unit=lab.unit,
            ref_range=lab.ref_range,
            collected_at=lab.collected_at,
            interpretation=_interpret_lab(lab),
        )
        for lab in payload.labs
    ]
    normalized_labs.sort(key=lambda x: (x.collected_at, x.lab_id))

    normalized_series: list[NormalizedBiomarkerSeries] = []
    for series in payload.biomarker_series:
        points = [
            NormalizedBiomarkerPoint(
                measured_at=p.measured_at,
                value=p.value,
                interpretation=_interpret_biomarker_point(series=series, point=p),
            )
            for p in series.points
        ]
        points.sort(key=lambda p: p.measured_at)
        if points:
            trend = _trend(first=points[0].value, last=points[-1].value)
            latest_interpretation = points[-1].interpretation
        else:
            trend = "stable"
            latest_interpretation = "normal"

        normalized_series.append(
            NormalizedBiomarkerSeries(
                series_id=series.series_id,
                code=series.code,
                name=series.name,
                unit=series.unit,
                ref_range=series.ref_range,
                points=points,
                trend=trend,
                latest_interpretation=latest_interpretation,
            )
        )
    normalized_series.sort(key=lambda s: s.series_id)

    return NormalizedPatient(
        case_id=payload.case_id,
        patient_id=payload.patient_id,
        generated_at=payload.generated_at,
        demographics=dict(sorted(payload.demographics.items())),
        labs=normalized_labs,
        genomics=sorted(payload.genomics, key=lambda g: g.variant_id),
        biomarker_series=normalized_series,
        medications=payload.medications,
        imaging=payload.imaging,
        history=payload.history,
        scenario_tags=sorted(payload.scenario_tags),
    )
