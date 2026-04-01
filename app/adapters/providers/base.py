from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.patient import NormalizedPatient


class LLMProvider(ABC):
    @abstractmethod
    async def generate_chr_draft(self, *, normalized: NormalizedPatient) -> dict[str, Any]:
        """
        Return a JSON-serializable dict matching `ComprehensiveHealthReportDraft`.

        Contract:
        - Must be structured JSON (no free-form markdown).
        - Must be deterministic for the same input when using the mock provider.
        """
