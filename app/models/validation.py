from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.failures import FailureCode


class ValidationIssue(BaseModel):
    code: FailureCode
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ValidationDecision(BaseModel):
    accepted: bool
    decided_at: datetime
    issues: list[ValidationIssue] = Field(default_factory=list)
