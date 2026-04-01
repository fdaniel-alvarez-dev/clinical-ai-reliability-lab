from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.evaluation import EvaluationResult
from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft, ComprehensiveHealthReportFinal
from app.models.validation import ValidationDecision
from app.storage.artifact_store import ArtifactStore
from app.workflows.biomarker_graph.models import BiomarkerConcern, BiomarkerGraph


class ReportExporter(ABC):
    @abstractmethod
    def export(
        self,
        *,
        store: ArtifactStore,
        normalized: NormalizedPatient,
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
        final: ComprehensiveHealthReportFinal,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        evaluation: EvaluationResult,
    ) -> dict[str, str]:
        """
        Persist artifacts and return a dict of artifact names -> stable references.
        """
