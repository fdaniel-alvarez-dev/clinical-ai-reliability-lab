from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft
from app.models.validation import ValidationDecision
from app.workflows.biomarker_graph.models import BiomarkerConcern


class ReportValidator(ABC):
    @abstractmethod
    def validate(
        self,
        *,
        normalized: NormalizedPatient,
        workflow: str,
        draft: ComprehensiveHealthReportDraft,
        concerns: list[BiomarkerConcern],
    ) -> ValidationDecision: ...
