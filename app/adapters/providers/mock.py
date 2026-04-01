from __future__ import annotations

from datetime import UTC
from typing import Any

from app.adapters.providers.base import LLMProvider
from app.models.patient import NormalizedPatient
from app.models.report import EvidenceRef, Finding, Recommendation
from app.services.normalizer import fingerprint_dict
from app.workflows.biomarker_graph.models import BiomarkerConcern


class MockProvider(LLMProvider):
    """
    Deterministic provider used by default so the repo works without paid APIs.

    It can also deterministically simulate failure modes via `scenario_tags`.
    """

    async def generate_chr_draft(
        self,
        *,
        normalized: NormalizedPatient,
        workflow: str,
        concerns: list[BiomarkerConcern],
    ) -> dict[str, Any]:
        findings: list[Finding] = []

        abnormal_labs = [lab for lab in normalized.labs if lab.interpretation != "normal"]
        normal_labs = [lab for lab in normalized.labs if lab.interpretation == "normal"]

        if workflow == "sequential_chr":
            for c in concerns:
                kind = c.evidence[0].kind if c.evidence else "history"
                category = "lab" if kind == "lab" else "biomarker"
                findings.append(
                    Finding(
                        finding_id=f"finding_concern_{c.concern_id}",
                        category=category,
                        title=c.title,
                        statement=c.statement,
                        evidence=c.evidence,
                        severity=c.severity,
                    )
                )

        # Genomics: include notable variants (synthetic annotations only).
        for v in normalized.genomics:
            if v.significance == "benign":
                continue
            findings.append(
                Finding(
                    finding_id=f"finding_gen_{v.variant_id}",
                    category="genomics",
                    title=f"Genomic marker: {v.gene} ({v.zygosity})",
                    statement=(
                        f"Synthetic genomic marker recorded: {v.gene} {v.variant}. "
                        f"Annotation label: {v.significance}."
                    ),
                    evidence=[EvidenceRef(kind="genomic_variant", id=v.variant_id)],
                    severity="info" if v.significance == "unknown" else "mild",
                )
            )

        if "omit_genomic_risk_marker" in normalized.scenario_tags:
            findings = [
                f
                for f in findings
                if not any(ref.kind == "genomic_variant" for ref in f.evidence)
            ]

        # Longitudinal biomarkers: include abnormal latest values and non-stable trends.
        for s in normalized.biomarker_series:
            if not s.points:
                continue
            if s.latest_interpretation == "normal" and s.trend == "stable":
                continue
            findings.append(
                Finding(
                    finding_id=f"finding_bio_{s.series_id}",
                    category="biomarker",
                    title=f"{s.name}: {s.latest_interpretation.upper()} ({s.trend})",
                    statement=(
                        f"{s.name} ({s.code}) is {s.latest_interpretation} with a {s.trend} trend "
                        f"based on {len(s.points)} synthetic measurement(s)."
                    ),
                    evidence=[EvidenceRef(kind="biomarker_series", id=s.series_id)],
                    severity="moderate" if s.latest_interpretation in {"high", "low"} else "info",
                )
            )

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
            removed = False
            remaining: list[Finding] = []
            for f in findings:
                if not removed and f.category == "lab":
                    removed = True
                    continue
                remaining.append(f)
            findings = remaining

        if "contradictory_biomarker_trend" in normalized.scenario_tags:
            for s in normalized.biomarker_series:
                if not s.points:
                    continue
                claimed = "decreasing" if s.trend != "decreasing" else "increasing"
                findings.insert(
                    0,
                    Finding(
                        finding_id="finding_biomarker_contradiction_1",
                        category="biomarker",
                        title=f"{s.name}: {s.latest_interpretation.upper()} ({claimed})",
                        statement=(
                            f"{s.name} ({s.code}) is {s.latest_interpretation} with a {claimed} trend."
                        ),
                        evidence=[EvidenceRef(kind="biomarker_series", id=s.series_id)],
                        severity="info",
                    ),
                )
                break

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

        if workflow == "sequential_chr" and concerns:
            for idx, c in enumerate(concerns, start=1):
                recs.append(
                    Recommendation(
                        rec_id=f"rec_concern_{idx}",
                        title=f"Review concern: {c.title}",
                        statement=(
                            "Discuss this concern with a licensed clinician and consider "
                            "follow-up questions or repeat measurements if clinically appropriate."
                        ),
                        rationale="Deterministic concern extracted from the biomarker graph stage.",
                        evidence=c.evidence,
                    )
                )

        input_fp = fingerprint_dict(normalized.model_dump(mode="json"))
        draft_payload: dict[str, Any] = {
            "schema_version": "chr_v1",
            "generated_at": normalized.generated_at.astimezone(UTC).isoformat(),
            "executive_summary": _executive_summary(
                normalized=normalized, findings=findings, workflow=workflow
            ),
            "findings": [f.model_dump(mode="json") for f in findings],
            "recommendations": [r.model_dump(mode="json") for r in recs],
            "input_fingerprint": input_fp,
            "draft_fingerprint": "pending",
        }
        draft_payload["draft_fingerprint"] = fingerprint_dict(draft_payload)
        return draft_payload


def _executive_summary(
    *, normalized: NormalizedPatient, findings: list[Finding], workflow: str
) -> str:
    abnormal_count = sum(1 for lab in normalized.labs if lab.interpretation != "normal")
    concern_count = sum(1 for f in findings if f.finding_id.startswith("finding_concern_"))
    prefix = ""
    if workflow == "easy_chr":
        prefix = "Easy CHR workflow: "
    if workflow == "functional_chr":
        prefix = "Functional CHR workflow: "
    if workflow == "sequential_chr":
        prefix = "Sequential CHR workflow: "
    if abnormal_count == 0:
        if concern_count:
            return (
                f"{prefix}{concern_count} concern(s) derived from the deterministic biomarker graph. "
                "All statements must be validated against the input evidence; unsupported claims should be rejected."
            )
        return f"{prefix}No abnormal lab findings detected in the provided synthetic dataset."
    return (
        f"{prefix}{abnormal_count} abnormal lab finding(s) detected in the provided synthetic dataset. "
        "All statements must be validated against the input evidence; unsupported claims should be rejected."
    )
