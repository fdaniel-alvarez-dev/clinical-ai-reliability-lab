from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.models.job import JobStatus, StoredJob


@dataclass(frozen=True)
class StoredReport:
    report_id: str
    workflow_id: str
    correlation_id: str
    created_at: datetime
    accepted: bool | None
    status: str
    final_json: dict[str, Any] | None
    evaluation_json: dict[str, Any] | None
    artifacts_json: dict[str, Any] | None


class SqliteReportRepository:
    def __init__(self, *, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reports (
              report_id TEXT PRIMARY KEY,
              workflow_id TEXT NOT NULL,
              correlation_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              status TEXT NOT NULL,
              accepted INTEGER,
              final_json TEXT,
              evaluation_json TEXT,
              artifacts_json TEXT
            )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              workflow TEXT NOT NULL,
              idempotency_key TEXT,
              payload_fingerprint TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              report_id TEXT NOT NULL,
              workflow_id TEXT NOT NULL,
              correlation_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              attempt_count INTEGER NOT NULL,
              max_attempts INTEGER NOT NULL,
              next_retry_at TEXT,
              last_error TEXT,
              UNIQUE(workflow, idempotency_key)
            )
            """)
        self._conn.commit()

    def create_report(
        self, *, report_id: str, workflow_id: str, correlation_id: str, status: str
    ) -> None:
        created_at = datetime.now(tz=UTC).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO reports(report_id, workflow_id, correlation_id, created_at, status)
            VALUES(?, ?, ?, ?, ?)
            """,
            (report_id, workflow_id, correlation_id, created_at, status),
        )
        self._conn.commit()

    def update_report(
        self,
        *,
        report_id: str,
        status: str,
        accepted: bool | None = None,
        final_json: dict[str, Any] | None = None,
        evaluation_json: dict[str, Any] | None = None,
        artifacts_json: dict[str, Any] | None = None,
    ) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE reports
            SET status = ?,
                accepted = COALESCE(?, accepted),
                final_json = COALESCE(?, final_json),
                evaluation_json = COALESCE(?, evaluation_json),
                artifacts_json = COALESCE(?, artifacts_json)
            WHERE report_id = ?
            """,
            (
                status,
                None if accepted is None else (1 if accepted else 0),
                None if final_json is None else json.dumps(final_json),
                None if evaluation_json is None else json.dumps(evaluation_json),
                None if artifacts_json is None else json.dumps(artifacts_json),
                report_id,
            ),
        )
        self._conn.commit()

    def get_report(self, *, report_id: str) -> StoredReport | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
        if row is None:
            return None

        accepted: bool | None
        if row["accepted"] is None:
            accepted = None
        else:
            accepted = bool(row["accepted"])

        return StoredReport(
            report_id=str(row["report_id"]),
            workflow_id=str(row["workflow_id"]),
            correlation_id=str(row["correlation_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            accepted=accepted,
            status=str(row["status"]),
            final_json=_loads_optional_obj(row["final_json"]),
            evaluation_json=_loads_optional_obj(row["evaluation_json"]),
            artifacts_json=_loads_optional_obj(row["artifacts_json"]),
        )

    def create_job(
        self,
        *,
        job_id: str,
        workflow: str,
        idempotency_key: str | None,
        payload_fingerprint: str,
        payload_json: dict[str, Any],
        report_id: str,
        workflow_id: str,
        correlation_id: str,
        status: JobStatus,
        max_attempts: int,
    ) -> None:
        now = datetime.now(tz=UTC).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO jobs(
              job_id, workflow, idempotency_key, payload_fingerprint, payload_json,
              report_id, workflow_id, correlation_id,
              created_at, updated_at, status, attempt_count, max_attempts, next_retry_at, last_error
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                workflow,
                idempotency_key,
                payload_fingerprint,
                json.dumps(payload_json),
                report_id,
                workflow_id,
                correlation_id,
                now,
                now,
                status.value,
                0,
                max_attempts,
                None,
                None,
            ),
        )
        self._conn.commit()

    def get_job(self, *, job_id: str) -> StoredJob | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return _row_to_job(row)

    def find_job_by_idempotency(
        self, *, workflow: str, idempotency_key: str
    ) -> StoredJob | None:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT * FROM jobs WHERE workflow = ? AND idempotency_key = ?",
            (workflow, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return _row_to_job(row)

    def update_job(
        self,
        *,
        job_id: str,
        status: JobStatus | None = None,
        attempt_count: int | None = None,
        next_retry_at: datetime | None = None,
        last_error: dict[str, Any] | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        now = (updated_at or datetime.now(tz=UTC)).isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE jobs
            SET updated_at = ?,
                status = COALESCE(?, status),
                attempt_count = COALESCE(?, attempt_count),
                next_retry_at = COALESCE(?, next_retry_at),
                last_error = COALESCE(?, last_error)
            WHERE job_id = ?
            """,
            (
                now,
                None if status is None else status.value,
                attempt_count,
                None if next_retry_at is None else next_retry_at.isoformat(),
                None if last_error is None else json.dumps(last_error),
                job_id,
            ),
        )
        self._conn.commit()


def _loads_optional_obj(v: Any) -> dict[str, Any] | None:
    if v is None:
        return None
    parsed: Any = json.loads(v)
    if not isinstance(parsed, dict):
        raise ValueError("Stored JSON payload was not an object.")
    return cast(dict[str, Any], parsed)


def _row_to_job(row: sqlite3.Row) -> StoredJob:
    status = JobStatus(str(row["status"]))
    next_retry_at = datetime.fromisoformat(row["next_retry_at"]) if row["next_retry_at"] else None

    payload = _loads_optional_obj(row["payload_json"])
    if payload is None:
        raise ValueError("Stored job payload_json was NULL.")

    last_error = _loads_optional_obj(row["last_error"])

    return StoredJob(
        job_id=str(row["job_id"]),
        workflow=str(row["workflow"]),
        idempotency_key=str(row["idempotency_key"]) if row["idempotency_key"] else None,
        payload_fingerprint=str(row["payload_fingerprint"]),
        payload_json=payload,
        report_id=str(row["report_id"]),
        workflow_id=str(row["workflow_id"]),
        correlation_id=str(row["correlation_id"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        status=status,
        attempt_count=int(row["attempt_count"]),
        max_attempts=int(row["max_attempts"]),
        next_retry_at=next_retry_at,
        last_error=last_error,
    )

