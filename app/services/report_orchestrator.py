from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from opentelemetry import trace
from pydantic import TypeAdapter

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
from app.storage.artifact_store import ArtifactStore
from app.storage.sqlite_repo import SqliteReportRepository
from app.validators.base import ReportValidator
from app.workflows.biomarker_graph import BiomarkerConcern, BiomarkerGraph, build_biomarker_graph
from app.workflows.chr.factory import normalize_workflow_name
from app.workflows.chr.names import CHRWorkflowName

tracer = trace.get_tracer(__name__)
_payload_adapter = TypeAdapter(SyntheticPatientPayload)


class ReportOrchestrator:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        validator: ReportValidator,
        evaluator: ReportEvaluator,
        exporter: ReportExporter,
        repo: SqliteReportRepository,
        artifact_store: ArtifactStore,
        workflow_timeout_s: float = 30.0,
        provider_max_attempts: int = 2,
        provider_retry_base_s: float = 0.2,
        provider_retry_max_s: float = 2.0,
    ) -> None:
        self._provider = provider
        self._validator = validator
        self._evaluator = evaluator
        self._exporter = exporter
        self._repo = repo
        self._artifact_store = artifact_store
        self._workflow_timeout_s = workflow_timeout_s
        self._provider_max_attempts = provider_max_attempts
        self._provider_retry_base_s = provider_retry_base_s
        self._provider_retry_max_s = provider_retry_max_s

    async def generate(
        self,
        *,
        payload: SyntheticPatientPayload | dict[str, object],
        workflow: str = "chr_v1",
        report_id: str | None = None,
        workflow_id: str | None = None,
        correlation_id: str | None = None,
        attempt: int | None = None,
    ) -> tuple[ComprehensiveHealthReportFinal, EvaluationResult, dict[str, str]]:
        workflow_name = normalize_workflow_name(workflow)
        report_id = report_id or new_report_id()
        workflow_id = workflow_id or new_workflow_id()
        correlation_id = correlation_id or new_correlation_id()

        if isinstance(payload, SyntheticPatientPayload):
            payload_model = payload
        else:
            payload_model = _payload_adapter.validate_python(payload)

        normalized: NormalizedPatient | None = None
        biomarker_graph: BiomarkerGraph | None = None
        concerns: list[BiomarkerConcern] = []

        existing = self._repo.get_report(report_id=report_id)
        if existing is None:
            self._repo.create_report(
                report_id=report_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                status="running",
            )
        else:
            self._repo.update_report(report_id=report_id, status="running")

        with tracer.start_as_current_span("workflow.generate", attributes={"report_id": report_id}):
            try:
                async with asyncio.timeout(self._workflow_timeout_s):
                    normalized = self._normalize(payload=payload_model)
                    biomarker_graph, concerns = self._biomarker_graph(normalized=normalized)
                    try:
                        draft = await self._draft(
                            normalized=normalized, workflow_name=workflow_name, concerns=concerns
                        )
                        validation = self._validate(
                            normalized=normalized,
                            workflow_name=workflow_name,
                            draft=draft,
                            concerns=concerns,
                        )
                        evaluation = self._evaluate(
                            normalized=normalized,
                            draft=draft,
                            validation=validation,
                            biomarker_graph=biomarker_graph,
                            concerns=concerns,
                        )
                    except ProviderOutputInvalidError as err:
                        validation = provider_output_invalid_decision(err=err)
                        draft = None
                        evaluation = self._evaluator.evaluate(
                            normalized=normalized,
                            draft=None,
                            validation=validation,
                            biomarker_graph=biomarker_graph,
                            concerns=concerns,
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
                        biomarker_graph=biomarker_graph,
                        concerns=concerns,
                        final=final,
                        draft=draft,
                        validation=validation,
                        evaluation=evaluation,
                        attempt=attempt,
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
                    report_id=report_id,
                    normalized=normalized,
                    biomarker_graph=biomarker_graph,
                    concerns=concerns,
                    final=final,
                    evaluation=evaluation,
                    attempt=attempt,
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

    def _biomarker_graph(
        self, *, normalized: NormalizedPatient
    ) -> tuple[BiomarkerGraph, list[BiomarkerConcern]]:
        with tracer.start_as_current_span(WorkflowStage.BIOMARKER_GRAPH) as span:
            graph, concerns = build_biomarker_graph(normalized=normalized)
            span.set_attribute("biomarker_graph.node_count", len(graph.nodes))
            span.set_attribute("biomarker_graph.edge_count", len(graph.edges))
            span.set_attribute("biomarker_graph.concern_count", len(concerns))
            return graph, concerns

    async def _draft(
        self,
        *,
        normalized: NormalizedPatient,
        workflow_name: CHRWorkflowName,
        concerns: list[BiomarkerConcern],
    ) -> ComprehensiveHealthReportDraft:
        with tracer.start_as_current_span(WorkflowStage.DRAFT):
            draft_dict = await self._draft_with_retries(
                normalized=normalized, workflow=workflow_name.value, concerns=concerns
            )
            try:
                return ComprehensiveHealthReportDraft.model_validate(draft_dict)
            except Exception as exc:
                decided_at = datetime.now(tz=UTC)
                raise ProviderOutputInvalidError(
                    decided_at=decided_at, message="Provider output failed schema validation."
                ) from exc

    async def _draft_with_retries(
        self,
        *,
        normalized: NormalizedPatient,
        workflow: str,
        concerns: list[BiomarkerConcern],
    ) -> dict[str, object]:
        last_exc: Exception | None = None
        for attempt in range(1, self._provider_max_attempts + 1):
            try:
                return await self._provider.generate_chr_draft(
                    normalized=normalized, workflow=workflow, concerns=concerns
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= self._provider_max_attempts:
                    break
                delay_s = min(self._provider_retry_max_s, self._provider_retry_base_s * (2 ** (attempt - 1)))
                if delay_s > 0:
                    await asyncio.sleep(delay_s)
        assert last_exc is not None
        raise last_exc

    def _validate(
        self,
        *,
        normalized: NormalizedPatient,
        workflow_name: CHRWorkflowName,
        draft: ComprehensiveHealthReportDraft,
        concerns: list[BiomarkerConcern],
    ) -> ValidationDecision:
        with tracer.start_as_current_span(WorkflowStage.VALIDATE):
            return self._validator.validate(
                normalized=normalized,
                workflow=workflow_name.value,
                draft=draft,
                concerns=concerns,
            )

    def _evaluate(
        self,
        *,
        normalized: NormalizedPatient,
        draft: ComprehensiveHealthReportDraft,
        validation: ValidationDecision,
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
    ) -> EvaluationResult:
        with tracer.start_as_current_span(WorkflowStage.EVALUATE):
            return self._evaluator.evaluate(
                normalized=normalized,
                draft=draft,
                validation=validation,
                biomarker_graph=biomarker_graph,
                concerns=concerns,
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
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
        final: ComprehensiveHealthReportFinal,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        evaluation: EvaluationResult,
        attempt: int | None,
    ) -> dict[str, str]:
        with tracer.start_as_current_span(WorkflowStage.EXPORT):
            prefix = report_id
            if attempt is not None:
                prefix = f"{prefix}/attempt_{attempt:02d}"
            store = self._artifact_store.scoped(prefix=prefix)
            return self._exporter.export(
                store=store,
                normalized=normalized,
                biomarker_graph=biomarker_graph,
                concerns=concerns,
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
        biomarker_graph: BiomarkerGraph | None,
        concerns: list[BiomarkerConcern],
        final: ComprehensiveHealthReportFinal,
        evaluation: EvaluationResult,
        attempt: int | None,
    ) -> dict[str, str]:
        prefix = report_id
        if attempt is not None:
            prefix = f"{prefix}/attempt_{attempt:02d}"
        store = self._artifact_store.scoped(prefix=prefix)
        index: dict[str, str] = {}

        def _write_json(name: str, payload: object) -> None:
            index[name] = store.put_json(name=name, payload=payload).ref

        if normalized is not None:
            _write_json("normalized_input.json", normalized.model_dump(mode="json"))
            graph = biomarker_graph
            if graph is None:
                graph, concerns = build_biomarker_graph(normalized=normalized)
            _write_json("biomarker_graph.json", graph.model_dump(mode="json"))
            _write_json("concerns.json", {"concerns": [c.model_dump(mode="json") for c in concerns]})
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
        index["rejection.md"] = store.put_text(name="rejection.md", content=rejection_md).ref

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
