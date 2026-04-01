from __future__ import annotations

from datetime import UTC, datetime

from app.evaluators.base import ReportEvaluator
from app.models.evaluation import EvaluationResult
from app.models.failures import FailureCode
from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft
from app.models.validation import ValidationDecision
from app.workflows.biomarker_graph.models import BiomarkerConcern, BiomarkerGraph


class CHRv1Evaluator(ReportEvaluator):
    """
    Simple, inspectable scoring.

    Evaluation is intentionally separate from validation:
    - Validation decides accept/reject.
    - Evaluation explains quality signals and preserves artifacts for review.
    """

    def evaluate(
        self,
        *,
        normalized: NormalizedPatient,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
    ) -> EvaluationResult:
        evaluated_at = datetime.now(tz=UTC)

        node_count = len(biomarker_graph.nodes)
        edge_count = len(biomarker_graph.edges)
        domain_count = sum(1 for n in biomarker_graph.nodes if n.kind == "domain")
        concern_count = len(concerns)
        domain_coverage = round(min(1.0, domain_count / 3.0), 4)

        abnormal_lab_ids = {lab.lab_id for lab in normalized.labs if lab.interpretation != "normal"}

        if draft is None:
            return EvaluationResult(
                evaluated_at=evaluated_at,
                scores={"overall": 0.0},
                notes=["No draft available for evaluation."],
                metrics={
                    "abnormal_lab_count": float(len(abnormal_lab_ids)),
                    "biomarker_graph_node_count": float(node_count),
                    "biomarker_graph_edge_count": float(edge_count),
                    "biomarker_graph_domain_coverage": float(domain_coverage),
                    "biomarker_concern_count": float(concern_count),
                },
            )

        referenced_lab_ids: set[str] = set()
        evidence_items = 0
        evidence_with_refs = 0

        for finding in draft.findings:
            evidence_items += 1
            if finding.evidence:
                evidence_with_refs += 1
            for ref in finding.evidence:
                if ref.kind == "lab":
                    referenced_lab_ids.add(ref.id)

        for rec in draft.recommendations:
            evidence_items += 1
            if rec.evidence:
                evidence_with_refs += 1
            for ref in rec.evidence:
                if ref.kind == "lab":
                    referenced_lab_ids.add(ref.id)

        traceability = (evidence_with_refs / evidence_items) if evidence_items else 0.0
        completeness = (
            (len(abnormal_lab_ids & referenced_lab_ids) / len(abnormal_lab_ids))
            if abnormal_lab_ids
            else 1.0
        )

        contradiction_risk = (
            1.0
            if any(i.code == FailureCode.VALIDATION_FAILED_CONTRADICTION for i in validation.issues)
            else 0.0
        )

        factual_consistency = 1.0 if validation.accepted else 0.0

        overall = round(
            0.40 * factual_consistency
            + 0.30 * completeness
            + 0.20 * traceability
            - 0.10 * contradiction_risk,
            4,
        )
        overall = max(0.0, min(1.0, overall))

        notes: list[str] = []
        if not validation.accepted:
            notes.append("Validation rejected the draft; scores reflect rejection.")

        return EvaluationResult(
            evaluated_at=evaluated_at,
            scores={
                "overall": overall,
                "factual_consistency": factual_consistency,
                "completeness": round(completeness, 4),
                "traceability": round(traceability, 4),
                "contradiction_risk": round(contradiction_risk, 4),
            },
            notes=notes,
            metrics={
                "abnormal_lab_count": float(len(abnormal_lab_ids)),
                "abnormal_lab_referenced_count": float(len(abnormal_lab_ids & referenced_lab_ids)),
                "evidence_items": float(evidence_items),
                "evidence_items_with_refs": float(evidence_with_refs),
                "biomarker_graph_node_count": float(node_count),
                "biomarker_graph_edge_count": float(edge_count),
                "biomarker_graph_domain_coverage": float(domain_coverage),
                "biomarker_concern_count": float(concern_count),
            },
        )
