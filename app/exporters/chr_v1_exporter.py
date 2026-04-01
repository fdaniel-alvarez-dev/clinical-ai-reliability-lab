from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from app.exporters.base import ReportExporter
from app.models.evaluation import EvaluationResult
from app.models.patient import NormalizedPatient
from app.models.report import ComprehensiveHealthReportDraft, ComprehensiveHealthReportFinal
from app.models.validation import ValidationDecision


class CHRv1Exporter(ReportExporter):
    def export(
        self,
        *,
        artifacts_dir: Path,
        normalized: NormalizedPatient,
        final: ComprehensiveHealthReportFinal,
        draft: ComprehensiveHealthReportDraft | None,
        validation: ValidationDecision,
        evaluation: EvaluationResult,
    ) -> dict[str, str]:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        index: dict[str, str] = {}

        def _write_json(name: str, payload: Any) -> None:
            path = artifacts_dir / name
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            )
            index[name] = str(path.relative_to(artifacts_dir.parent))

        _write_json("normalized_input.json", normalized.model_dump(mode="json"))
        if draft is not None:
            _write_json("model_draft.json", draft.model_dump(mode="json"))
        _write_json("validation_decision.json", validation.model_dump(mode="json"))
        _write_json("evaluation.json", evaluation.model_dump(mode="json"))
        _write_json("final.json", final.model_dump(mode="json"))

        if final.accepted and draft is not None:
            md = render_markdown_report(final=final, draft=draft, evaluation=evaluation)
            md_path = artifacts_dir / "report.md"
            md_path.write_text(md, encoding="utf-8")
            index["report.md"] = str(md_path.relative_to(artifacts_dir.parent))

            pdf_path = artifacts_dir / "report.pdf"
            render_pdf_report(pdf_path=pdf_path, final=final, draft=draft, evaluation=evaluation)
            index["report.pdf"] = str(pdf_path.relative_to(artifacts_dir.parent))
        else:
            md = render_markdown_rejection(
                final=final, validation=validation, evaluation=evaluation
            )
            md_path = artifacts_dir / "rejection.md"
            md_path.write_text(md, encoding="utf-8")
            index["rejection.md"] = str(md_path.relative_to(artifacts_dir.parent))

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


def render_pdf_report(
    *,
    pdf_path: Path,
    final: ComprehensiveHealthReportFinal,
    draft: ComprehensiveHealthReportDraft,
    evaluation: EvaluationResult,
) -> None:
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=letter, title="Comprehensive Health Report (CHR)"
    )
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
