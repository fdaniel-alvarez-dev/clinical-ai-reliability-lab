from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


@dataclass(frozen=True)
class StoredJob:
    job_id: str
    workflow: str
    idempotency_key: str | None
    payload_fingerprint: str
    payload_json: dict[str, Any]

    report_id: str
    workflow_id: str
    correlation_id: str

    created_at: datetime
    updated_at: datetime
    status: JobStatus
    attempt_count: int
    max_attempts: int
    next_retry_at: datetime | None
    last_error: dict[str, Any] | None

