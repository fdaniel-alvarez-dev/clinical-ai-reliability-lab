from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _payload_ok() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "case_id": "pw_ui_ok",
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


@pytest.mark.skipif(os.getenv("RUN_PLAYWRIGHT") != "1", reason="Set RUN_PLAYWRIGHT=1 to enable.")
def test_ui_smoke_playwright(tmp_path: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    from fastapi.testclient import TestClient

    from app.main import create_app

    os.environ["DB_PATH"] = str(tmp_path / "reports.sqlite")
    os.environ["ARTIFACTS_DIR"] = str(tmp_path / "artifacts")
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["PROVIDER_MAX_ATTEMPTS"] = "1"

    app = create_app()
    client = TestClient(app)
    gen = client.post("/v1/reports/generate", json=_payload_ok())
    assert gen.status_code == 200
    report_id = gen.json()["report_id"]

    # Mount the ASGI app into a real HTTP server via TestClient's base_url.
    base_url = str(client.base_url).rstrip("/")

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{base_url}/ui/reports/{report_id}")
        page.wait_for_selector("[data-testid='decision']")
        assert page.locator("[data-testid='decision']").inner_text() == "ACCEPTED"
        browser.close()
