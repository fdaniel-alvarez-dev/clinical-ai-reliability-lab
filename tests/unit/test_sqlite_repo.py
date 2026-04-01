from __future__ import annotations

from pathlib import Path

from app.storage.sqlite_repo import SqliteReportRepository


def test_sqlite_repo_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "reports.sqlite"
    repo = SqliteReportRepository(db_path=str(db_path))

    repo.create_report(
        report_id="rpt_1", workflow_id="wf_1", correlation_id="corr_1", status="running"
    )
    repo.update_report(
        report_id="rpt_1",
        status="completed",
        accepted=True,
        final_json={"a": 1},
        evaluation_json={"score": 0.9},
        artifacts_json={"report.json": "rpt_1/report.json"},
    )

    stored = repo.get_report(report_id="rpt_1")
    assert stored is not None
    assert stored.report_id == "rpt_1"
    assert stored.accepted is True
    assert stored.status == "completed"
    assert stored.final_json == {"a": 1}
    assert stored.evaluation_json == {"score": 0.9}
    assert stored.artifacts_json == {"report.json": "rpt_1/report.json"}
