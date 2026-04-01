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
            }
        ],
        "scenario_tags": tags,
    }


@pytest.mark.asyncio
async def test_ui_renders_accepted_report(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PROVIDER_MAX_ATTEMPTS", "1")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        gen = await client.post("/v1/reports/generate", json=_payload(case_id="ui_ok", tags=[]))
        assert gen.status_code == 200
        report_id = gen.json()["report_id"]

        ui = await client.get(f"/ui/reports/{report_id}")
        assert ui.status_code == 200
        assert "data-testid=\"title\"" in ui.text
        assert "data-testid=\"decision\"" in ui.text
        assert "ACCEPTED" in ui.text
        assert f"/v1/reports/{report_id}" in ui.text


@pytest.mark.asyncio
async def test_ui_renders_rejected_report(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PROVIDER_MAX_ATTEMPTS", "1")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        gen = await client.post(
            "/v1/reports/generate",
            json=_payload(case_id="ui_reject", tags=["hallucinated_claim_risk"]),
        )
        assert gen.status_code == 200
        report_id = gen.json()["report_id"]

        ui = await client.get(f"/ui/reports/{report_id}")
        assert ui.status_code == 200
        assert "REJECTED" in ui.text

