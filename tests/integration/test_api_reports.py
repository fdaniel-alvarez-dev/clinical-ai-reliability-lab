from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from app.main import create_app


def _payload(*, case_id: str, tags: list[str]) -> dict[str, object]:
    return {
        "schema_version": "v1",
        "case_id": case_id,
        "patient_id": "synthetic_001",
        "generated_at": datetime(2026, 4, 1, 12, 0, tzinfo=UTC).isoformat(),
        "demographics": {"age": "45", "sex": "F"},
        "labs": [
            {
                "lab_id": "lab_ldl",
                "code": "LDL_C",
                "name": "LDL Cholesterol",
                "value": 140.0,
                "unit": "mg/dL",
                "ref_range": {"low": 0.0, "high": 100.0},
                "collected_at": datetime(2026, 3, 1, 9, 0, tzinfo=UTC).isoformat(),
            },
            {
                "lab_id": "lab_a1c",
                "code": "A1C",
                "name": "HbA1c",
                "value": 5.2,
                "unit": "%",
                "ref_range": {"low": 4.0, "high": 5.6},
                "collected_at": datetime(2026, 3, 1, 9, 5, tzinfo=UTC).isoformat(),
            },
        ],
        "medications": [],
        "imaging": [],
        "history": [],
        "scenario_tags": tags,
    }


@pytest.mark.asyncio
async def test_generate_then_fetch_report_artifacts(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200

        gen = await client.post("/v1/reports/generate", json=_payload(case_id="case_ok", tags=[]))
        assert gen.status_code == 200
        body = gen.json()
        assert body["accepted"] is True
        report_id = body["report_id"]

        rep = await client.get(f"/v1/reports/{report_id}")
        assert rep.status_code == 200
        ev = await client.get(f"/v1/reports/{report_id}/evaluation")
        assert ev.status_code == 200
        art = await client.get(f"/v1/reports/{report_id}/artifacts")
        assert art.status_code == 200
        artifacts = art.json()["artifacts"]
        assert "report.md" in artifacts
        assert "report.pdf" in artifacts


@pytest.mark.asyncio
async def test_generate_rejected_case_returns_rejection_artifact(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        gen = await client.post(
            "/v1/reports/generate",
            json=_payload(case_id="case_reject", tags=["hallucinated_claim_risk"]),
        )
        assert gen.status_code == 200
        body = gen.json()
        assert body["accepted"] is False
        report_id = body["report_id"]

        art = await client.get(f"/v1/reports/{report_id}/artifacts")
        assert art.status_code == 200
        artifacts = art.json()["artifacts"]
        assert "rejection.md" in artifacts
        assert "model_draft.json" in artifacts
