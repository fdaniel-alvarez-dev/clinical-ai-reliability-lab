from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from app.models.patient import LabResult, NormalizedLab, NormalizedPatient, SyntheticPatientPayload


def _interpret_lab(lab: LabResult) -> Literal["low", "normal", "high"]:
    if lab.value < lab.ref_range.low:
        return "low"
    if lab.value > lab.ref_range.high:
        return "high"
    return "normal"


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

    return NormalizedPatient(
        case_id=payload.case_id,
        patient_id=payload.patient_id,
        generated_at=payload.generated_at,
        demographics=dict(sorted(payload.demographics.items())),
        labs=normalized_labs,
        medications=payload.medications,
        imaging=payload.imaging,
        history=payload.history,
        scenario_tags=sorted(payload.scenario_tags),
    )
