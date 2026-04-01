from __future__ import annotations

import re
from datetime import UTC, datetime

from app.models.failures import FailureCode
from app.models.patient import NormalizedLab, NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft, EvidenceRef, Recommendation
from app.models.validation import ValidationDecision, ValidationIssue
from app.validators.base import ReportValidator

_STATUS_WORD_RE = re.compile(r"\b(high|low|normal)\b", flags=re.IGNORECASE)


class CHRv1DeterministicValidator(ReportValidator):
    """
    Deterministic validator for `chr_v1`.

    Design stance:
    - The model may draft, but this validator decides what can pass.
    - If evidence is insufficient, reject explicitly.
    """

    def validate(
        self, *, normalized: NormalizedPatient, draft: ComprehensiveHealthReportDraft
    ) -> ValidationDecision:
        issues: list[ValidationIssue] = []

        lab_by_id = {lab.lab_id: lab for lab in normalized.labs}
        med_names = {m.name for m in normalized.medications}
        imaging_keys = {(i.modality, i.performed_at.isoformat()) for i in normalized.imaging}
        history_keys = {(h.occurred_at.isoformat(), h.summary) for h in normalized.history}

        issues.extend(self._validate_no_medical_claims(draft=draft))
        issues.extend(self._validate_evidence_refs(draft=draft, lab_by_id=lab_by_id))
        issues.extend(self._validate_traceability(draft=draft))
        issues.extend(self._validate_lab_findings_consistency(draft=draft, lab_by_id=lab_by_id))
        issues.extend(self._validate_abnormal_omissions(draft=draft, lab_by_id=lab_by_id))
        issues.extend(
            self._validate_recommendations_evidence(
                draft=draft,
                med_names=med_names,
                imaging_keys=imaging_keys,
                history_keys=history_keys,
            )
        )

        return ValidationDecision(
            accepted=len(issues) == 0,
            decided_at=datetime.now(tz=UTC),
            issues=issues,
        )

    def _validate_traceability(
        self, *, draft: ComprehensiveHealthReportDraft
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not draft.input_fingerprint or draft.input_fingerprint == "n/a":
            issues.append(
                ValidationIssue(
                    code=FailureCode.INSUFFICIENT_EVIDENCE,
                    message="Missing input_fingerprint; traceability is required.",
                )
            )
        if not draft.draft_fingerprint or draft.draft_fingerprint == "n/a":
            issues.append(
                ValidationIssue(
                    code=FailureCode.INSUFFICIENT_EVIDENCE,
                    message="Missing draft_fingerprint; traceability is required.",
                )
            )
        return issues

    def _validate_evidence_refs(
        self, *, draft: ComprehensiveHealthReportDraft, lab_by_id: dict[str, NormalizedLab]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        def _check_evidence(evidence: list[EvidenceRef], where: str, item_id: str) -> None:
            for ref in evidence:
                if ref.kind == "lab" and ref.id not in lab_by_id:
                    issues.append(
                        ValidationIssue(
                            code=FailureCode.VALIDATION_FAILED_UNSUPPORTED_CLAIM,
                            message=f"Evidence reference {ref.id!r} not found in labs.",
                            details={"where": where, "id": item_id, "ref": ref.model_dump()},
                        )
                    )

        for f in draft.findings:
            _check_evidence(f.evidence, "finding", f.finding_id)
        for r in draft.recommendations:
            _check_evidence(r.evidence, "recommendation", r.rec_id)
        return issues

    def _validate_abnormal_omissions(
        self, *, draft: ComprehensiveHealthReportDraft, lab_by_id: dict[str, NormalizedLab]
    ) -> list[ValidationIssue]:
        abnormal_lab_ids = {
            lab_id for lab_id, lab in lab_by_id.items() if lab.interpretation != "normal"
        }
        referenced_lab_ids: set[str] = set()
        for f in draft.findings:
            for ref in f.evidence:
                if ref.kind == "lab":
                    referenced_lab_ids.add(ref.id)

        missing = sorted(abnormal_lab_ids - referenced_lab_ids)
        if missing:
            return [
                ValidationIssue(
                    code=FailureCode.VALIDATION_FAILED_CRITICAL_OMISSION,
                    message="Draft omitted critical abnormal lab finding(s).",
                    details={"missing_lab_ids": missing},
                )
            ]
        return []

    def _validate_lab_findings_consistency(
        self, *, draft: ComprehensiveHealthReportDraft, lab_by_id: dict[str, NormalizedLab]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        for finding in draft.findings:
            if finding.category != "lab":
                continue
            lab_refs = [ref for ref in finding.evidence if ref.kind == "lab"]
            if not lab_refs:
                continue

            for ref in lab_refs:
                lab = lab_by_id.get(ref.id)
                if lab is None:
                    continue
                interpretation = getattr(lab, "interpretation", None)
                claimed = _claimed_status(text=f"{finding.title} {finding.statement}")
                if claimed is None:
                    continue
                if interpretation != claimed:
                    issues.append(
                        ValidationIssue(
                            code=FailureCode.VALIDATION_FAILED_CONTRADICTION,
                            message="Lab finding contradicts the normalized lab interpretation.",
                            details={
                                "finding_id": finding.finding_id,
                                "lab_id": ref.id,
                                "claimed": claimed,
                                "actual": interpretation,
                            },
                        )
                    )

        return issues

    def _validate_recommendations_evidence(
        self,
        *,
        draft: ComprehensiveHealthReportDraft,
        med_names: set[str],
        imaging_keys: set[tuple[str, str]],
        history_keys: set[tuple[str, str]],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for rec in draft.recommendations:
            if not rec.evidence:
                issues.append(
                    ValidationIssue(
                        code=FailureCode.INSUFFICIENT_EVIDENCE,
                        message="Recommendation missing evidence references.",
                        details={"rec_id": rec.rec_id},
                    )
                )
            if _contains_prescriptive_language(rec=rec):
                issues.append(
                    ValidationIssue(
                        code=FailureCode.VALIDATION_FAILED_UNSUPPORTED_CLAIM,
                        message="Recommendation contains prescriptive language (not allowed in this demo).",
                        details={"rec_id": rec.rec_id},
                    )
                )
            if rec.safety_note.strip() != "Educational demo only. Not medical advice.":
                issues.append(
                    ValidationIssue(
                        code=FailureCode.VALIDATION_FAILED_SCHEMA,
                        message="Missing or altered safety_note; expected explicit non-medical-advice note.",
                        details={"rec_id": rec.rec_id},
                    )
                )
        return issues

    def _validate_no_medical_claims(
        self, *, draft: ComprehensiveHealthReportDraft
    ) -> list[ValidationIssue]:
        text = " ".join(
            [draft.executive_summary]
            + [f"{f.title} {f.statement}" for f in draft.findings]
            + [f"{r.title} {r.statement} {r.rationale}" for r in draft.recommendations]
        ).lower()
        prohibited = [
            "diagnosis",
            "diagnose",
            "prescribe",
            "prescription",
            "take ",
            "take a ",
            "increase dose",
            "decrease dose",
        ]
        if any(p in text for p in prohibited):
            return [
                ValidationIssue(
                    code=FailureCode.VALIDATION_FAILED_UNSUPPORTED_CLAIM,
                    message="Draft contains diagnosis/prescribing language that is out of scope for this demo.",
                    details={"matched": [p for p in prohibited if p in text]},
                )
            ]
        return []


def _claimed_status(*, text: str) -> str | None:
    match = _STATUS_WORD_RE.search(text)
    if not match:
        return None
    return match.group(1).lower()


def _contains_prescriptive_language(*, rec: Recommendation) -> bool:
    text = f"{rec.title} {rec.statement}".lower()
    hard_verbs = ["start ", "begin ", "initiate ", "stop ", "switch ", "increase ", "decrease "]
    if any(v in text for v in hard_verbs):
        # Allow "discuss with a clinician" patterns.
        if "discuss" in text or "clinician" in text or "physician" in text:
            return False
        return True
    return False
