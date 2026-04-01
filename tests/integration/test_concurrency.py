from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest
from pytest import MonkeyPatch

from app.main import create_app


@pytest.mark.asyncio
async def test_two_concurrent_generations_do_not_collide(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload_raw = json.loads(
            Path("datasets/case_01_stable_patient.json").read_text(encoding="utf-8")
        )
        assert isinstance(payload_raw, dict)
        payload: dict[str, object] = payload_raw

        async def _gen() -> dict[str, object]:
            resp = await client.post("/v1/reports/generate", json=payload)
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body, dict)
            return body

        a, b = await asyncio.gather(_gen(), _gen())
        assert a["accepted"] is True
        assert b["accepted"] is True
        assert a["report_id"] != b["report_id"]

        artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
        for run in (a, b):
            artifacts = run["artifacts"]
            assert isinstance(artifacts, dict)
            assert "report.md" in artifacts
            assert (artifacts_dir / artifacts["report.md"]).exists()
            assert "report.pdf" in artifacts
            assert (artifacts_dir / artifacts["report.pdf"]).exists()
