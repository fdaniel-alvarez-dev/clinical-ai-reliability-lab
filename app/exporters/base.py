from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.evaluation import EvaluationResult
from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft, ComprehensiveHealthReportFinal
from app.models.validation import ValidationDecision
from app.workflows.biomarker_graph.models import BiomarkerConcern, BiomarkerGraph


class ReportExporter(ABC):
    @abstractmethod
    def export(
        self,
        *,
        artifacts_dir: Path,
        normalized: NormalizedPatient,
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
        final: ComprehensiveHealthReportFinal,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        evaluation: EvaluationResult,
    ) -> dict[str, str]:
        """
        Persist artifacts to disk and return a dict of artifact names -> relative paths.
        """
