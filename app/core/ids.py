from __future__ import annotations

import secrets


def new_report_id() -> str:
    return f"rpt_{secrets.token_urlsafe(12)}"


def new_workflow_id() -> str:
    return f"wf_{secrets.token_urlsafe(12)}"


def new_correlation_id() -> str:
    return f"corr_{secrets.token_urlsafe(12)}"


def new_job_id() -> str:
    return f"job_{secrets.token_urlsafe(12)}"
