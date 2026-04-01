from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft
from app.models.validation import ValidationDecision


class ReportValidator(ABC):
    @abstractmethod
    def validate(
        self, *, normalized: NormalizedPatient, draft: ComprehensiveHealthReportDraft
    ) -> ValidationDecision: ...
