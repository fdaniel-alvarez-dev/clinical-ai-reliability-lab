from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from app.main import create_app


def _load_dataset(path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _read_json(path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


EXPECTED_CODES_BY_DATASET: dict[str, set[str]] = {
    "case_02_missing_critical_context.json": {
        "INSUFFICIENT_EVIDENCE",
        "VALIDATION_FAILED_UNSUPPORTED_CLAIM",
    },
    "case_03_hallucinated_claim_risk.json": {"VALIDATION_FAILED_UNSUPPORTED_CLAIM"},
    "case_04_contradictory_lab_history.json": {"VALIDATION_FAILED_CONTRADICTION"},
    "case_05_abnormal_biomarker_omitted.json": {"VALIDATION_FAILED_CRITICAL_OMISSION"},
}


@pytest.mark.asyncio
async def test_repeatability_case_06_has_stable_fingerprints(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _load_dataset(Path("datasets/case_06_repeatability_check.json"))

        run_a = (await client.post("/v1/reports/generate", json=payload)).json()
        run_b = (await client.post("/v1/reports/generate", json=payload)).json()

        assert run_a["accepted"] is True
        assert run_b["accepted"] is True
        assert run_a["report_id"] != run_b["report_id"]

        artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
        draft_a = _read_json(artifacts_dir / run_a["artifacts"]["model_draft.json"])
        draft_b = _read_json(artifacts_dir / run_b["artifacts"]["model_draft.json"])

        assert draft_a["input_fingerprint"] == draft_b["input_fingerprint"]
        assert draft_a["draft_fingerprint"] == draft_b["draft_fingerprint"]


@pytest.mark.asyncio
@pytest.mark.parametrize("dataset_name", sorted(EXPECTED_CODES_BY_DATASET.keys()))
async def test_rejected_datasets_have_validation_issue_codes_and_rejection_artifact(
    tmp_path: Path, monkeypatch: MonkeyPatch, dataset_name: str
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _load_dataset(Path("datasets") / dataset_name)
        gen = await client.post("/v1/reports/generate", json=payload)
        body = gen.json()
        assert body["accepted"] is False
        artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])

        validation = _read_json(artifacts_dir / body["artifacts"]["validation_decision.json"])
        assert validation["accepted"] is False
        issues = validation.get("issues")
        assert isinstance(issues, list)
        codes = {i.get("code") for i in issues if isinstance(i, dict)}
        expected = EXPECTED_CODES_BY_DATASET[dataset_name]
        assert codes & expected, f"expected one of {expected}, got {codes}"

        assert "rejection.md" in body["artifacts"]
        assert (artifacts_dir / body["artifacts"]["rejection.md"]).exists()
