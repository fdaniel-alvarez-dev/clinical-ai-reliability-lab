from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest import MonkeyPatch

from app.adapters.providers.base import LLMProvider
from app.main import create_app
from app.models.patient import NormalizedPatient


def _payload_ok() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "case_id": "case_ok",
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
        "medications": [],
        "imaging": [],
        "history": [],
        "scenario_tags": [],
    }


class InvalidJSONProvider(LLMProvider):
    async def generate_chr_draft(self, *, normalized: NormalizedPatient) -> dict[str, Any]:
        return {"not": "a chr_v1 draft"}


class SlowProvider(LLMProvider):
    def __init__(self, *, sleep_s: float) -> None:
        self._sleep_s = sleep_s

    async def generate_chr_draft(self, *, normalized: NormalizedPatient) -> dict[str, Any]:
        await asyncio.sleep(self._sleep_s)
        return {"not": "a chr_v1 draft"}


@pytest.mark.asyncio
async def test_provider_output_invalid_is_rejected_with_reason(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    app.state.orchestrator._provider = InvalidJSONProvider()  # type: ignore[attr-defined]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        gen = await client.post("/v1/reports/generate", json=_payload_ok())
        assert gen.status_code == 200
        body = gen.json()
        assert body["accepted"] is False

        artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
        validation_path = artifacts_dir / body["artifacts"]["validation_decision.json"]
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        codes = {i.get("code") for i in validation.get("issues", []) if isinstance(i, dict)}
        assert "PROVIDER_OUTPUT_INVALID" in codes
        assert "rejection.md" in body["artifacts"]


@pytest.mark.asyncio
async def test_workflow_timeout_exports_failure_artifacts(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    app.state.orchestrator._provider = SlowProvider(sleep_s=0.2)  # type: ignore[attr-defined]
    app.state.orchestrator._workflow_timeout_s = 0.01  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        gen = await client.post("/v1/reports/generate", json=_payload_ok())
        assert gen.status_code == 200
        body = gen.json()
        assert body["status"] == "failed"
        assert body["accepted"] is False

        artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
        assert "rejection.md" in body["artifacts"]
        assert (artifacts_dir / body["artifacts"]["rejection.md"]).exists()
        final = json.loads(
            (artifacts_dir / body["artifacts"]["final.json"]).read_text(encoding="utf-8")
        )
        assert isinstance(final, dict)
        rejection = final.get("rejection")
        assert isinstance(rejection, dict)
        assert rejection.get("code") == "WORKFLOW_TIMEOUT"
