from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.evaluation import EvaluationResult
from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft
from app.models.validation import ValidationDecision
from app.workflows.biomarker_graph.models import BiomarkerConcern, BiomarkerGraph


class ReportEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        *,
        normalized: NormalizedPatient,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
    ) -> EvaluationResult: ...
