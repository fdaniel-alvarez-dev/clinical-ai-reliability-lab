from __future__ import annotations

from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from app.exporters.base import ReportExporter
from app.models.evaluation import EvaluationResult
from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft, ComprehensiveHealthReportFinal
from app.models.validation import ValidationDecision
from app.storage.artifact_store import ArtifactStore
from app.workflows.biomarker_graph.models import BiomarkerConcern, BiomarkerGraph


class CHRv1Exporter(ReportExporter):
    def export(
        self,
        *,
        store: ArtifactStore,
        normalized: NormalizedPatient,
        biomarker_graph: BiomarkerGraph,
        concerns: list[BiomarkerConcern],
        final: ComprehensiveHealthReportFinal,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        evaluation: EvaluationResult,
    ) -> dict[str, str]:
        index: dict[str, str] = {}

        def _write_json(name: str, payload: Any) -> None:
            addr = store.put_json(name=name, payload=payload)
            index[name] = addr.ref

        _write_json("normalized_input.json", normalized.model_dump(mode="json"))
        _write_json("biomarker_graph.json", biomarker_graph.model_dump(mode="json"))
        _write_json("concerns.json", {"concerns": [c.model_dump(mode="json") for c in concerns]})
        if draft is not None:
            _write_json("model_draft.json", draft.model_dump(mode="json"))
        _write_json("validation_decision.json", validation.model_dump(mode="json"))
        _write_json("evaluation.json", evaluation.model_dump(mode="json"))
        _write_json("final.json", final.model_dump(mode="json"))

        if final.accepted and draft is not None:
            md = render_markdown_report(final=final, draft=draft, evaluation=evaluation)
            index["report.md"] = store.put_text(name="report.md", content=md).ref

            pdf_bytes = render_pdf_bytes(final=final, draft=draft, evaluation=evaluation)
            index["report.pdf"] = store.put_bytes(name="report.pdf", content=pdf_bytes).ref
        else:
            md = render_markdown_rejection(
                final=final, validation=validation, evaluation=evaluation
            )
            index["rejection.md"] = store.put_text(name="rejection.md", content=md).ref

        _write_json("artifacts_index.json", index)
        return index


def render_markdown_report(
    *,
    final: ComprehensiveHealthReportFinal,
    draft: ComprehensiveHealthReportDraft,
    evaluation: EvaluationResult,
) -> str:
    lines: list[str] = []
    lines.append("# Comprehensive Health Report (CHR)")
    lines.append("")
    lines.append("**Synthetic demo only. Not medical advice.**")
    lines.append("")
    lines.append(f"- report_id: `{final.report_id}`")
    lines.append(f"- workflow_id: `{final.workflow_id}`")
    lines.append(f"- correlation_id: `{final.correlation_id}`")
    lines.append("- decision: `ACCEPTED`")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(draft.executive_summary.strip())
    lines.append("")
    lines.append("## Findings")
    for f in draft.findings:
        lines.append(f"- **{f.title}** — {f.statement}")
    lines.append("")
    lines.append("## Recommendations (Educational)")
    for r in draft.recommendations:
        lines.append(f"- **{r.title}** — {r.statement}")
        lines.append(f"  - Rationale: {r.rationale}")
        lines.append(f"  - Safety: {r.safety_note}")
    lines.append("")
    lines.append("## Evaluation")
    for k, v in sorted(evaluation.scores.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_markdown_rejection(
    *,
    final: ComprehensiveHealthReportFinal,
    validation: ValidationDecision,
    evaluation: EvaluationResult,
) -> str:
    lines: list[str] = []
    lines.append("# Report Rejected")
    lines.append("")
    lines.append("**Synthetic demo only. Not medical advice.**")
    lines.append("")
    lines.append(f"- report_id: `{final.report_id}`")
    lines.append(f"- workflow_id: `{final.workflow_id}`")
    lines.append(f"- correlation_id: `{final.correlation_id}`")
    lines.append("- decision: `REJECTED`")
    lines.append("")
    lines.append("## Rejection Reasons")
    for issue in validation.issues:
        lines.append(f"- `{issue.code}`: {issue.message}")
    lines.append("")
    lines.append("## Evaluation (for inspection)")
    for k, v in sorted(evaluation.scores.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_pdf_bytes(
    *,
    final: ComprehensiveHealthReportFinal,
    draft: ComprehensiveHealthReportDraft,
    evaluation: EvaluationResult,
) -> bytes:
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="Comprehensive Health Report (CHR)")
    styles = getSampleStyleSheet()
    story: list[Flowable] = []

    story.append(Paragraph("Comprehensive Health Report (CHR)", styles["Title"]))
    story.append(Paragraph("Synthetic demo only. Not medical advice.", styles["Italic"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Report ID: {final.report_id}", styles["Normal"]))
    story.append(Paragraph(f"Workflow ID: {final.workflow_id}", styles["Normal"]))
    story.append(Paragraph(f"Correlation ID: {final.correlation_id}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive Summary", styles["Heading2"]))
    story.append(Paragraph(draft.executive_summary, styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Findings", styles["Heading2"]))
    for f in draft.findings:
        story.append(Paragraph(f"<b>{f.title}</b>: {f.statement}", styles["Normal"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Recommendations (Educational)", styles["Heading2"]))
    for r in draft.recommendations:
        story.append(Paragraph(f"<b>{r.title}</b>: {r.statement}", styles["Normal"]))
        story.append(Paragraph(f"Rationale: {r.rationale}", styles["Normal"]))
        story.append(Paragraph(f"Safety: {r.safety_note}", styles["Normal"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Evaluation", styles["Heading2"]))
    for k, v in sorted(evaluation.scores.items()):
        story.append(Paragraph(f"{k}: {v}", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
