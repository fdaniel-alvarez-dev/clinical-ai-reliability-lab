from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models.job import JobStatus
from app.storage.sqlite_repo import SqliteReportRepository


def test_jobs_repo_round_trip_and_idempotency(tmp_path: Path) -> None:
    db_path = tmp_path / "reports.sqlite"
    repo = SqliteReportRepository(db_path=str(db_path))

    repo.create_job(
        job_id="job_1",
        workflow="chr_v1",
        idempotency_key="idem_1",
        payload_fingerprint="fp_1",
        payload_json={"schema_version": "v1", "case_id": "case_x"},
        report_id="rpt_1",
        workflow_id="wf_1",
        correlation_id="corr_1",
        status=JobStatus.queued,
        max_attempts=2,
    )
    stored = repo.get_job(job_id="job_1")
    assert stored is not None
    assert stored.status == JobStatus.queued
    assert stored.attempt_count == 0

    found = repo.find_job_by_idempotency(workflow="chr_v1", idempotency_key="idem_1")
    assert found is not None
    assert found.job_id == "job_1"

    repo.update_job(job_id="job_1", status=JobStatus.running, attempt_count=1)
    stored2 = repo.get_job(job_id="job_1")
    assert stored2 is not None
    assert stored2.status == JobStatus.running
    assert stored2.attempt_count == 1

    now = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    repo.update_job(job_id="job_1", next_retry_at=now, last_error={"x": 1}, updated_at=now)
    stored3 = repo.get_job(job_id="job_1")
    assert stored3 is not None
    assert stored3.next_retry_at == now
    assert stored3.last_error == {"x": 1}

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_job(
            job_id="job_2",
            workflow="chr_v1",
            idempotency_key="idem_1",
            payload_fingerprint="fp_1",
            payload_json={"schema_version": "v1", "case_id": "case_x"},
            report_id="rpt_2",
            workflow_id="wf_2",
            correlation_id="corr_2",
            status=JobStatus.queued,
            max_attempts=2,
        )

