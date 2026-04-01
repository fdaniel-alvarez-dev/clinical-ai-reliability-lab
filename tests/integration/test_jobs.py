from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from pytest import MonkeyPatch

from app.adapters.providers.base import LLMProvider
from app.main import create_app
from app.models.patient import NormalizedPatient
from app.workflows.biomarker_graph.models import BiomarkerConcern


def _payload_ok() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "case_id": "case_job_ok",
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
        "scenario_tags": [],
    }


async def _wait_for_status(
    client: httpx.AsyncClient, job_id: str, *, want: str, timeout_s: float = 2.0
) -> dict[str, Any]:
    start = asyncio.get_running_loop().time()
    while True:
        resp = await client.get(f"/v1/jobs/{job_id}")
        assert resp.status_code == 200
        raw = resp.json()
        job = raw.get("job")
        assert isinstance(job, dict)
        if job["status"] == want:
            return cast(dict[str, Any], job)
        if asyncio.get_running_loop().time() - start > timeout_s:
            raise AssertionError(f"Timed out waiting for job {job_id} to reach {want}, got {job['status']}")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_jobs_create_poll_and_idempotency(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("JOB_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("PROVIDER_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_RETRY_BASE_S", "0")
    monkeypatch.setenv("PROVIDER_RETRY_MAX_S", "0")

    app = create_app()
    app.state.job_runner.start()  # type: ignore[attr-defined]
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Idempotency-Key": "idem_jobs_1"}
            r1 = await client.post("/v1/jobs?workflow=chr_v1", json=_payload_ok(), headers=headers)
            assert r1.status_code == 200
            job_id = r1.json()["job_id"]

            r2 = await client.post("/v1/jobs?workflow=chr_v1", json=_payload_ok(), headers=headers)
            assert r2.status_code == 200
            assert r2.json()["job_id"] == job_id

            done = await _wait_for_status(client, job_id, want="succeeded")
            assert done["report_id"]
    finally:
        await app.state.job_runner.stop()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_jobs_retry_creates_attempt_artifacts(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "reports.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("JOB_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("PROVIDER_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("PROVIDER_RETRY_BASE_S", "0")
    monkeypatch.setenv("PROVIDER_RETRY_MAX_S", "0")

    class SlowOnceProvider(LLMProvider):
        def __init__(self) -> None:
            self._calls = 0

        async def generate_chr_draft(
            self, *, normalized: NormalizedPatient, workflow: str, concerns: list[BiomarkerConcern]
        ) -> dict[str, Any]:
            self._calls += 1
            if self._calls == 1:
                await asyncio.sleep(0.05)
            # Minimal valid draft. Validator should accept.
            input_fp = "in_fp"
            payload: dict[str, Any] = {
                "schema_version": "chr_v1",
                "generated_at": normalized.generated_at.isoformat(),
                "executive_summary": "Synthetic summary.",
                "findings": [
                    {
                        "finding_id": "finding_lab_ldl",
                        "category": "lab",
                        "title": "LDL Cholesterol: HIGH",
                        "statement": "LDL is high at 140 mg/dL.",
                        "evidence": [{"kind": "lab", "id": "lab_ldl"}],
                        "severity": "moderate",
                    }
                ],
                "recommendations": [
                    {
                        "rec_id": "rec_1",
                        "title": "Follow-up",
                        "statement": "Discuss with a licensed clinician.",
                        "rationale": "Abnormal value in synthetic input.",
                        "evidence": [{"kind": "lab", "id": "lab_ldl"}],
                        "safety_note": "Educational demo only. Not medical advice.",
                    }
                ],
                "input_fingerprint": input_fp,
                "draft_fingerprint": "dr_fp",
            }
            return payload

    app = create_app()
    app.state.orchestrator._provider = SlowOnceProvider()  # type: ignore[attr-defined]
    app.state.orchestrator._workflow_timeout_s = 0.03  # type: ignore[attr-defined]
    app.state.job_runner.start()  # type: ignore[attr-defined]

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/v1/jobs?workflow=chr_v1", json=_payload_ok())
            assert r.status_code == 200
            job_id = r.json()["job_id"]
            report_id = r.json()["report_id"]

            done = await _wait_for_status(client, job_id, want="succeeded")
            assert done["attempt_count"] == 2

            artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
            attempt_1 = artifacts_dir / report_id / "attempt_01"
            attempt_2 = artifacts_dir / report_id / "attempt_02"
            assert (attempt_1 / "rejection.md").exists()
            assert (attempt_2 / "report.md").exists()
            assert (attempt_2 / "biomarker_graph.json").exists()

            rep = await client.get(f"/v1/reports/{report_id}")
            assert rep.status_code == 200
    finally:
        await app.state.job_runner.stop()  # type: ignore[attr-defined]
