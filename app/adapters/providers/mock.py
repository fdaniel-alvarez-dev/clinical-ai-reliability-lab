from __future__ import annotations

from datetime import UTC
from typing import Any

from app.adapters.providers.base import LLMProvider
from app.models.patient import NormalizedPatient
from app.models.report import EvidenceRef, Finding, Recommendation
from app.services.normalizer import fingerprint_dict


class MockProvider(LLMProvider):
    """
    Deterministic provider used by default so the repo works without paid APIs.

    It can also deterministically simulate failure modes via `scenario_tags`.
    """

    async def generate_chr_draft(self, *, normalized: NormalizedPatient) -> dict[str, Any]:
        findings: list[Finding] = []

        abnormal_labs = [lab for lab in normalized.labs if lab.interpretation != "normal"]
        normal_labs = [lab for lab in normalized.labs if lab.interpretation == "normal"]

        for lab in abnormal_labs:
            findings.append(
                Finding(
                    finding_id=f"finding_{lab.lab_id}",
                    category="lab",
                    title=f"{lab.name}: {lab.interpretation.upper()}",
                    statement=(
                        f"{lab.name} ({lab.code}) is {lab.interpretation} at {lab.value} {lab.unit} "
                        f"(reference {lab.ref_range.low}-{lab.ref_range.high} {lab.unit})."
                    ),
                    evidence=[EvidenceRef(kind="lab", id=lab.lab_id)],
                    severity="moderate" if lab.interpretation in {"high", "low"} else "info",
                )
            )

        if "omit_abnormal_biomarker" in normalized.scenario_tags and abnormal_labs:
            findings = findings[1:]

        if "contradictory_lab_history" in normalized.scenario_tags and abnormal_labs:
            first = abnormal_labs[0]
            findings.insert(
                0,
                Finding(
                    finding_id="finding_contradiction_1",
                    category="lab",
                    title=f"{first.name}: NORMAL (claimed)",
                    statement=(
                        f"{first.name} ({first.code}) is normal at {first.value} {first.unit}."
                    ),
                    evidence=[EvidenceRef(kind="lab", id=first.lab_id)],
                    severity="info",
                ),
            )

        if "hallucinated_claim_risk" in normalized.scenario_tags:
            findings.append(
                Finding(
                    finding_id="finding_hallucinated_1",
                    category="lab",
                    title="Vitamin D: NORMAL",
                    statement="Vitamin D (25-OH) is normal.",
                    evidence=[EvidenceRef(kind="lab", id="lab_ghost_999")],
                    severity="info",
                )
            )

        recs: list[Recommendation] = []
        if abnormal_labs:
            recs.append(
                Recommendation(
                    rec_id="rec_1",
                    title="Follow-up with clinician for abnormal results",
                    statement=(
                        "Discuss the abnormal findings with a licensed clinician and consider "
                        "repeat testing if clinically appropriate."
                    ),
                    rationale="Abnormal values were detected in the synthetic input labs.",
                    evidence=[EvidenceRef(kind="lab", id=abnormal_labs[0].lab_id)],
                )
            )
        else:
            if normal_labs:
                recs.append(
                    Recommendation(
                        rec_id="rec_1",
                        title="Continue routine monitoring",
                        statement="Continue routine monitoring and healthy lifestyle habits.",
                        rationale="All reviewed labs are within reference ranges in the synthetic input.",
                        evidence=[EvidenceRef(kind="lab", id=normal_labs[0].lab_id)],
                    )
                )

        if "missing_critical_context" in normalized.scenario_tags:
            recs.append(
                Recommendation(
                    rec_id="rec_unsupported_1",
                    title="Start high-intensity statin",
                    statement="Start a high-intensity statin immediately.",
                    rationale="Elevated LDL requires medication.",
                    evidence=[],
                )
            )

        input_fp = fingerprint_dict(normalized.model_dump(mode="json"))
        draft_payload: dict[str, Any] = {
            "schema_version": "chr_v1",
            "generated_at": normalized.generated_at.astimezone(UTC).isoformat(),
            "executive_summary": _executive_summary(normalized=normalized, findings=findings),
            "findings": [f.model_dump(mode="json") for f in findings],
            "recommendations": [r.model_dump(mode="json") for r in recs],
            "input_fingerprint": input_fp,
            "draft_fingerprint": "pending",
        }
        draft_payload["draft_fingerprint"] = fingerprint_dict(draft_payload)
        return draft_payload


def _executive_summary(*, normalized: NormalizedPatient, findings: list[Finding]) -> str:
    abnormal_count = sum(1 for lab in normalized.labs if lab.interpretation != "normal")
    if abnormal_count == 0:
        return "No abnormal lab findings detected in the provided synthetic dataset."
    return (
        f"{abnormal_count} abnormal lab finding(s) detected in the provided synthetic dataset. "
        "All statements must be validated against the input evidence; unsupported claims should be rejected."
    )
