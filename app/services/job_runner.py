from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from opentelemetry import trace

from app.models.failures import FailureCode
from app.models.job import JobStatus
from app.services.report_orchestrator import ReportOrchestrator
from app.storage.sqlite_repo import SqliteReportRepository

tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class JobRunnerConfig:
    max_attempts: int
    retry_base_s: float
    retry_max_s: float


class JobRunner:
    def __init__(
        self,
        *,
        repo: SqliteReportRepository,
        orchestrator: ReportOrchestrator,
        config: JobRunnerConfig,
    ) -> None:
        self._repo = repo
        self._orchestrator = orchestrator
        self._config = config
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def enqueue(self, *, job_id: str) -> None:
        self._queue.put_nowait(job_id)

    async def _worker_loop(self) -> None:
        while not self._stop.is_set():
            job_id = await self._queue.get()
            try:
                await self._run_job(job_id=job_id)
            finally:
                self._queue.task_done()

    async def _run_job(self, *, job_id: str) -> None:
        job = self._repo.get_job(job_id=job_id)
        if job is None:
            return
        if job.status in {JobStatus.succeeded, JobStatus.failed}:
            return

        attempt = job.attempt_count + 1
        self._repo.update_job(job_id=job_id, status=JobStatus.running, attempt_count=attempt)

        with tracer.start_as_current_span("jobs.run", attributes={"job_id": job_id, "attempt": attempt}):
            try:
                final, _evaluation, _artifacts = await self._orchestrator.generate(
                    payload=job.payload_json,
                    workflow=job.workflow,
                    report_id=job.report_id,
                    workflow_id=job.workflow_id,
                    correlation_id=job.correlation_id,
                    attempt=attempt,
                )

                timeout = (
                    isinstance(final.rejection, dict)
                    and final.rejection.get("code") == FailureCode.WORKFLOW_TIMEOUT
                )
                if timeout and attempt < min(job.max_attempts, self._config.max_attempts):
                    await self._schedule_retry(job_id=job_id, attempt=attempt, reason="workflow_timeout")
                    return

                self._repo.update_job(job_id=job_id, status=JobStatus.succeeded, last_error=None)
            except Exception as exc:
                if attempt < min(job.max_attempts, self._config.max_attempts):
                    await self._schedule_retry(job_id=job_id, attempt=attempt, reason=type(exc).__name__)
                    return
                self._repo.update_job(
                    job_id=job_id,
                    status=JobStatus.failed,
                    last_error={"type": type(exc).__name__, "message": str(exc)},
                )

    async def _schedule_retry(self, *, job_id: str, attempt: int, reason: str) -> None:
        delay_s = min(self._config.retry_max_s, self._config.retry_base_s * (2 ** (attempt - 1)))
        now = datetime.now(tz=UTC)
        next_retry_at = now + timedelta(seconds=delay_s)
        self._repo.update_job(
            job_id=job_id,
            status=JobStatus.queued,
            next_retry_at=next_retry_at,
            last_error={"retry_reason": reason, "next_retry_at": next_retry_at.isoformat()},
        )
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        self.enqueue(job_id=job_id)
