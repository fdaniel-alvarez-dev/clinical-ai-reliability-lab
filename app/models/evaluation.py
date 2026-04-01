from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    evaluated_at: datetime
    scores: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
