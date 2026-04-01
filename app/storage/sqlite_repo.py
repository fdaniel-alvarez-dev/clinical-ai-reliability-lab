from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


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

        def _loads(v: Any) -> dict[str, Any] | None:
            if v is None:
                return None
            parsed: Any = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Stored JSON payload was not an object.")
            return cast(dict[str, Any], parsed)

        accepted: bool | None
        if row["accepted"] is None:
            accepted = None
        else:
            accepted = bool(row["accepted"])

        return StoredReport(
            report_id=row["report_id"],
            workflow_id=row["workflow_id"],
            correlation_id=row["correlation_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            accepted=accepted,
            status=row["status"],
            final_json=_loads(row["final_json"]),
            evaluation_json=_loads(row["evaluation_json"]),
            artifacts_json=_loads(row["artifacts_json"]),
        )
