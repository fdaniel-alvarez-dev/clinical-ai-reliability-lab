from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from opentelemetry import trace

from app.adapters.providers.base import LLMProvider
from app.core.ids import new_correlation_id, new_report_id, new_workflow_id
from app.evaluators.base import ReportEvaluator
from app.exporters.base import ReportExporter
from app.models.evaluation import EvaluationResult
from app.models.failures import FailureCode, WorkflowStage
from app.models.patient import NormalizedPatient, SyntheticPatientPayload
from app.models.report import ComprehensiveHealthReportDraft, ComprehensiveHealthReportFinal
from app.models.validation import ValidationDecision, ValidationIssue
from app.services.normalizer import normalize_patient
from app.storage.sqlite_repo import SqliteReportRepository
from app.validators.base import ReportValidator

tracer = trace.get_tracer(__name__)


class ReportOrchestrator:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        validator: ReportValidator,
        evaluator: ReportEvaluator,
        exporter: ReportExporter,
        repo: SqliteReportRepository,
        artifacts_dir: str,
        workflow_timeout_s: float = 30.0,
    ) -> None:
        self._provider = provider
        self._validator = validator
        self._evaluator = evaluator
        self._exporter = exporter
        self._repo = repo
        self._artifacts_dir = Path(artifacts_dir)
        self._workflow_timeout_s = workflow_timeout_s

    async def generate(
        self, *, payload: SyntheticPatientPayload
    ) -> tuple[ComprehensiveHealthReportFinal, EvaluationResult, dict[str, str]]:
        report_id = new_report_id()
        workflow_id = new_workflow_id()
        correlation_id = new_correlation_id()

        normalized: NormalizedPatient | None = None

        self._repo.create_report(
            report_id=report_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            status="running",
        )

        with tracer.start_as_current_span("workflow.generate", attributes={"report_id": report_id}):
            try:
                async with asyncio.timeout(self._workflow_timeout_s):
                    normalized = self._normalize(payload=payload)
                    try:
                        draft = await self._draft(normalized=normalized)
                        validation = self._validate(normalized=normalized, draft=draft)
                        evaluation = self._evaluate(
                            normalized=normalized, draft=draft, validation=validation
                        )
                    except ProviderOutputInvalidError as err:
                        validation = provider_output_invalid_decision(err=err)
                        draft = None
                        evaluation = self._evaluator.evaluate(
                            normalized=normalized, draft=None, validation=validation
                        )
                    final = self._finalize(
                        report_id=report_id,
                        workflow_id=workflow_id,
                        correlation_id=correlation_id,
                        draft=draft,
                        validation=validation,
                    )
                    artifacts_index = self._export(
                        report_id=report_id,
                        normalized=normalized,
                        final=final,
                        draft=draft,
                        validation=validation,
                        evaluation=evaluation,
                    )

                    self._repo.update_report(
                        report_id=report_id,
                        status="completed",
                        accepted=final.accepted,
                        final_json=final.model_dump(mode="json"),
                        evaluation_json=evaluation.model_dump(mode="json"),
                        artifacts_json=artifacts_index,
                    )
                    return final, evaluation, artifacts_index
            except TimeoutError:
                final = ComprehensiveHealthReportFinal(
                    report_id=report_id,
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    accepted=False,
                    decision_at=datetime.now(tz=UTC),
                    draft=None,
                    rejection={
                        "code": FailureCode.WORKFLOW_TIMEOUT,
                        "message": "Workflow exceeded timeout.",
                    },
                )
                evaluation = EvaluationResult(
                    evaluated_at=datetime.now(tz=UTC),
                    scores={"overall": 0.0},
                    notes=["Workflow timeout."],
                )
                artifacts_index_timeout = self._export_timeout_failure(
                    report_id=report_id, normalized=normalized, final=final, evaluation=evaluation
                )
                self._repo.update_report(
                    report_id=report_id,
                    status="failed",
                    accepted=False,
                    final_json=final.model_dump(mode="json"),
                    evaluation_json=evaluation.model_dump(mode="json"),
                    artifacts_json=artifacts_index_timeout,
                )
                return final, evaluation, artifacts_index_timeout

    def _normalize(self, *, payload: SyntheticPatientPayload) -> NormalizedPatient:
        with tracer.start_as_current_span(WorkflowStage.NORMALIZE):
            return normalize_patient(payload)

    async def _draft(self, *, normalized: NormalizedPatient) -> ComprehensiveHealthReportDraft:
        with tracer.start_as_current_span(WorkflowStage.DRAFT):
            draft_dict = await self._provider.generate_chr_draft(normalized=normalized)
            try:
                return ComprehensiveHealthReportDraft.model_validate(draft_dict)
            except Exception as exc:
                decided_at = datetime.now(tz=UTC)
                raise ProviderOutputInvalidError(
                    decided_at=decided_at, message="Provider output failed schema validation."
                ) from exc

    def _validate(
        self, *, normalized: NormalizedPatient, draft: ComprehensiveHealthReportDraft
    ) -> ValidationDecision:
        with tracer.start_as_current_span(WorkflowStage.VALIDATE):
            return self._validator.validate(normalized=normalized, draft=draft)

    def _evaluate(
        self,
        *,
        normalized: NormalizedPatient,
        draft: ComprehensiveHealthReportDraft,
        validation: ValidationDecision,
    ) -> EvaluationResult:
        with tracer.start_as_current_span(WorkflowStage.EVALUATE):
            return self._evaluator.evaluate(
                normalized=normalized, draft=draft, validation=validation
            )

    def _finalize(
        self,
        *,
        report_id: str,
        workflow_id: str,
        correlation_id: str,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
    ) -> ComprehensiveHealthReportFinal:
        if validation.accepted:
            if draft is None:
                raise RuntimeError("Invariant violation: accepted=True requires a draft.")
            return ComprehensiveHealthReportFinal(
                report_id=report_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                accepted=True,
                decision_at=validation.decided_at,
                draft=draft,
                rejection=None,
            )
        return ComprehensiveHealthReportFinal(
            report_id=report_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            accepted=False,
            decision_at=validation.decided_at,
            draft=None,
            rejection={
                "issues": [issue.model_dump(mode="json") for issue in validation.issues],
            },
        )

    def _export(
        self,
        *,
        report_id: str,
        normalized: NormalizedPatient,
        final: ComprehensiveHealthReportFinal,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        evaluation: EvaluationResult,
    ) -> dict[str, str]:
        with tracer.start_as_current_span(WorkflowStage.EXPORT):
            run_dir = self._artifacts_dir / report_id
            run_dir.mkdir(parents=True, exist_ok=True)
            return self._exporter.export(
                artifacts_dir=run_dir,
                normalized=normalized,
                final=final,
                draft=draft,
                validation=validation,
                evaluation=evaluation,
            )

    def _export_timeout_failure(
        self,
        *,
        report_id: str,
        normalized: NormalizedPatient | None,
        final: ComprehensiveHealthReportFinal,
        evaluation: EvaluationResult,
    ) -> dict[str, str]:
        run_dir = self._artifacts_dir / report_id
        run_dir.mkdir(parents=True, exist_ok=True)
        index: dict[str, str] = {}

        def _write_json(name: str, payload: object) -> None:
            path = run_dir / name
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            index[name] = str(path.relative_to(run_dir.parent))

        if normalized is not None:
            _write_json("normalized_input.json", normalized.model_dump(mode="json"))
        _write_json("evaluation.json", evaluation.model_dump(mode="json"))
        _write_json("final.json", final.model_dump(mode="json"))

        rejection_md = (
            "# Workflow Failed\n\n"
            "**Synthetic demo only. Not medical advice.**\n\n"
            f"- report_id: `{final.report_id}`\n"
            f"- workflow_id: `{final.workflow_id}`\n"
            f"- correlation_id: `{final.correlation_id}`\n"
            f"- failure: `{FailureCode.WORKFLOW_TIMEOUT}`\n\n"
            "The workflow exceeded the configured timeout and did not complete.\n"
        )
        md_path = run_dir / "rejection.md"
        md_path.write_text(rejection_md, encoding="utf-8")
        index["rejection.md"] = str(md_path.relative_to(run_dir.parent))

        _write_json("artifacts_index.json", index)
        return index


class ProviderOutputInvalidError(Exception):
    def __init__(self, *, decided_at: datetime, message: str) -> None:
        super().__init__(message)
        self.decided_at = decided_at
        self.message = message


def provider_output_invalid_decision(*, err: ProviderOutputInvalidError) -> ValidationDecision:
    return ValidationDecision(
        accepted=False,
        decided_at=err.decided_at,
        issues=[
            ValidationIssue(
                code=FailureCode.PROVIDER_OUTPUT_INVALID,
                message=err.message,
                details={},
            )
        ],
    )
