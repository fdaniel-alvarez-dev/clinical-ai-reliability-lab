from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from app.main import create_app


def _load_dataset(path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


DATASET_EXPECTATIONS: list[tuple[str, bool]] = [
    ("case_01_stable_patient.json", True),
    ("case_02_missing_critical_context.json", False),
    ("case_03_hallucinated_claim_risk.json", False),
    ("case_04_contradictory_lab_history.json", False),
    ("case_05_abnormal_biomarker_omitted.json", False),
    ("case_06_repeatability_check.json", True),
    ("case_07_genomics_risk_marker_omitted.json", False),
    ("case_08_biomarker_trend_contradiction.json", False),
    ("case_09_genomics_and_longitudinal_biomarkers_ok.json", True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("dataset_name", "expected_accepted"), DATASET_EXPECTATIONS)
async def test_e2e_datasets_expected_accept_reject(
    tmp_path: Path, monkeypatch: MonkeyPatch, dataset_name: str, expected_accepted: bool
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _load_dataset(Path("datasets") / dataset_name)
        gen = await client.post("/v1/reports/generate", json=payload)
        assert gen.status_code == 200
        body = gen.json()
        assert body["accepted"] is expected_accepted
