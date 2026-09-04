"""Render output/report.pdf from the PDF scorecard. Does not change JSON/Markdown reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _text(value: Any) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_report_pdf(scorecard: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleFR", parent=styles["Heading1"], fontSize=16, spaceAfter=8)
    heading = ParagraphStyle("HeadFR", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("BodyFR", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("SmallFR", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#444444"))

    story: list[Any] = [
        Paragraph("FirstRound AI — Interview Scorecard", title),
        Paragraph("Recruiter artifact. Not shown to the candidate-facing interview UI.", small),
        Spacer(1, 8),
        Paragraph(
            f"<b>Candidate:</b> {_text(scorecard.get('candidate_name'))}<br/>"
            f"<b>Role:</b> {_text(scorecard.get('role'))}<br/>"
            f"<b>Interview date:</b> {_text(scorecard.get('interview_date'))}<br/>"
            f"<b>Duration:</b> {_text(scorecard.get('duration_seconds'))} seconds<br/>"
            f"<b>Status:</b> {_text(scorecard.get('interview_status'))}<br/>"
            f"<b>Sample mode:</b> {_text(scorecard.get('sample_mode'))}",
            body,
        ),
        Paragraph("Decision", heading),
        Paragraph(
            f"<b>Overall score (1–5, evidence-gated):</b> {_text(scorecard.get('overall_score'))}<br/>"
            f"<b>Mean confidence:</b> {_text(scorecard.get('mean_confidence'))}<br/>"
            f"<b>Recommendation:</b> {_text(scorecard.get('recommendation'))}<br/>"
            f"<b>Reasoning:</b> {_text(scorecard.get('recommendation_reasoning'))}<br/>"
            f"<b>Legacy internal score (0–100):</b> {_text(scorecard.get('legacy_overall_score_100'))} "
            f"({_text(scorecard.get('legacy_recommendation'))})",
            body,
        ),
    ]

    rows = [["Competency", "Score", "Confidence", "Evidence quote", "Reasoning"]]
    for item in scorecard.get("competencies") or []:
        score = item.get("score")
        rows.append(
            [
                Paragraph(_text(item.get("name")), small),
                Paragraph("—" if score is None else _text(score), small),
                Paragraph(_text(item.get("confidence")), small),
                Paragraph(_text(item.get("evidence_quote") or "None"), small),
                Paragraph(_text(item.get("reasoning") or ""), small),
            ]
        )
    table = Table(rows, colWidths=[1.2 * inch, 0.6 * inch, 0.8 * inch, 2.4 * inch, 2.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e2630")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([Paragraph("Competencies", heading), table])

    def _bullets(title_text: str, items: list[Any]) -> None:
        story.append(Paragraph(title_text, heading))
        values = [str(item) for item in items if str(item).strip()]
        if not values:
            story.append(Paragraph("None recorded.", body))
            return
        for item in values:
            story.append(Paragraph(f"• {_text(item)}", body))

    _bullets("Strengths", list(scorecard.get("strengths") or []))
    _bullets("Concerns", list(scorecard.get("concerns") or []))
    flag_lines = []
    for flag in scorecard.get("guardrail_flags") or []:
        if isinstance(flag, dict):
            flag_lines.append(
                f"{flag.get('type')}: {flag.get('reason') or flag.get('competency') or ''}"
            )
        else:
            flag_lines.append(str(flag))
    _bullets("Guardrail flags", flag_lines)
    story.append(Paragraph("GitHub grounding", heading))
    story.append(
        Paragraph(
            f"GitHub-grounded questions asked: {_text(scorecard.get('github_grounded_questions_asked'))}<br/>"
            f"Questions attempted: {_text(scorecard.get('questions_attempted'))} of "
            f"{_text(scorecard.get('questions_total'))}",
            body,
        )
    )
    story.append(Paragraph("Limitations", heading))
    story.append(
        Paragraph(
            "Competency scores are refused unless a candidate-transcript quote of at least 12 characters "
            "appears verbatim. This interview may be partial. LiveKit reconnection after a dropped call is "
            "not implemented; SQLite restores controller state only. This PDF is a recruiter artifact and "
            "is not shown on the candidate frontend.",
            body,
        )
    )
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    doc.build(story)
    return path
