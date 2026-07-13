"""
PDF export for Claros.

Primary path: place answers onto the original worksheet PDF using layout regions.
Legacy path: reconstruct a ReportLab PDF for manifests without layout metadata.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from io import BytesIO
from typing import List

import fitz
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from manifest import validate_bbox_within_page
from parser import normalize_worksheet_text

_MAX_ANSWER_CHARS = 4000
_MIN_FONT_SIZE = 7.0
_MAX_FONT_SIZE = 12.0


class LayoutExportError(ValueError):
    """Raised when one or more answers cannot be placed into their regions."""

    def __init__(self, message: str, question_ids: list[int]):
        super().__init__(message)
        self.question_ids = question_ids


def strip_latex_dollars(s: str) -> str:
    return re.sub(r"\$([^$]+)\$", r"\1", s) if s else ""


def build_export_pdf(
    title: str,
    questions: List[dict],
    answers: List[dict],
) -> bytes:
    """
    Legacy reconstructed export. questions = [{"id": 1, "text": "..."}],
    answers = [{"question_id": 1, "answer_text": "..."}].
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "QuestionHead",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=6,
    )
    body_style = styles["Normal"]

    story = []
    story.append(Paragraph("Claros - Assignment Answers", title_style))
    safe_title = normalize_worksheet_text(title)
    story.append(Paragraph(safe_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), body_style))
    story.append(Spacer(1, 0.25 * inch))

    answer_by_id = {
        a["question_id"]: strip_latex_dollars(
            normalize_worksheet_text(a.get("answer_text", "") or "")
        )
        for a in answers
    }

    for q in questions:
        qid = q.get("id", 0)
        qtext = normalize_worksheet_text(q.get("text") or "")
        qtext = qtext.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(f"<b>Question {qid}</b>: {qtext}", heading_style))
        ans = normalize_worksheet_text(answer_by_id.get(qid) or "")
        ans = ans.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        story.append(Paragraph(ans or "(No answer)", body_style))
        story.append(Spacer(1, 0.15 * inch))
        story.append(HRFlowable(width="100%", thickness=0.5, color="gray"))
        story.append(Spacer(1, 0.2 * inch))

    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            ParagraphStyle("Footer", parent=body_style, fontSize=8, textColor="gray"),
        )
    )

    doc.build(story)
    return buf.getvalue()


def _resolved_answer_bbox(
    question: dict,
    pages_by_index: dict[int, dict],
    overrides_by_id: dict[int, dict],
) -> tuple[int, list[float]] | None:
    qid = int(question["id"])
    override = overrides_by_id.get(qid)
    if override:
        page_index = int(override["page_index"])
        page = pages_by_index.get(page_index)
        if page is None:
            raise LayoutExportError(f"layout override for question {qid} references unknown page", [qid])
        bbox = validate_bbox_within_page(
            override["answer_bbox"],
            page_width=float(page["width_points"]),
            page_height=float(page["height_points"]),
            label=f"layout_overrides question {qid}",
        )
        return page_index, bbox

    bbox = question.get("answer_bbox")
    page_index = question.get("page_index")
    if bbox is None or page_index is None:
        return None
    page = pages_by_index.get(int(page_index))
    if page is None:
        return None
    validated = validate_bbox_within_page(
        bbox,
        page_width=float(page["width_points"]),
        page_height=float(page["height_points"]),
        label=f"answer_bbox question {qid}",
    )
    return int(page_index), validated


def _textbox_fits(page_width: float, page_height: float, rect: fitz.Rect, text: str, fontsize: float) -> bool:
    """Probe fit on a scratch page so failed attempts never touch the original."""
    probe = fitz.open()
    try:
        scratch = probe.new_page(width=page_width, height=page_height)
        rc = scratch.insert_textbox(
            rect,
            text,
            fontname="helv",
            fontsize=fontsize,
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0, 0, 0),
        )
        return rc >= 0
    finally:
        probe.close()


def _fit_textbox(page, rect: fitz.Rect, text: str) -> bool:
    """Insert multiline text into rect, shrinking font until it fits. Returns False on overflow."""
    fontsize = _MAX_FONT_SIZE
    chosen = None
    while fontsize >= _MIN_FONT_SIZE:
        if _textbox_fits(page.rect.width, page.rect.height, rect, text, fontsize):
            chosen = fontsize
            break
        fontsize -= 0.5
    if chosen is None:
        return False
    rc = page.insert_textbox(
        rect,
        text,
        fontname="helv",
        fontsize=chosen,
        align=fitz.TEXT_ALIGN_LEFT,
        color=(0, 0, 0),
    )
    return rc >= 0


def build_layout_export_pdf(
    original_pdf_bytes: bytes,
    questions: list[dict],
    answers: list[dict],
    *,
    pages: list[dict] | None = None,
    layout_overrides: list[dict] | None = None,
) -> bytes:
    """
    Place answered text onto the original PDF inside answer regions.
    Unanswered questions are left blank (no placeholder). Unresolved regions without
    a valid manual override cause a 422-style LayoutExportError when an answer exists.
    """
    pages_by_index = {int(p["page_index"]): p for p in (pages or [])}
    overrides_by_id = {int(o["question_id"]): o for o in (layout_overrides or [])}
    answer_by_id = {
        int(a["question_id"]): strip_latex_dollars(
            normalize_worksheet_text((a.get("answer_text") or "")[:_MAX_ANSWER_CHARS])
        ).strip()
        for a in answers
    }

    try:
        doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError("PDF could not be opened") from exc

    # If pages metadata is missing, derive from the PDF.
    if not pages_by_index:
        pages_by_index = {
            i: {
                "page_index": i,
                "width_points": float(page.rect.width),
                "height_points": float(page.rect.height),
            }
            for i, page in enumerate(doc)
        }

    overflow_ids: list[int] = []
    unresolved_ids: list[int] = []

    try:
        questions_by_id = {int(q["id"]): q for q in questions}
        for qid, answer_text in sorted(answer_by_id.items()):
            if not answer_text:
                continue
            question = questions_by_id.get(qid)
            if question is None:
                continue
            resolved = _resolved_answer_bbox(question, pages_by_index, overrides_by_id)
            if resolved is None:
                unresolved_ids.append(qid)
                continue
            page_index, bbox = resolved
            if page_index < 0 or page_index >= doc.page_count:
                unresolved_ids.append(qid)
                continue
            page = doc.load_page(page_index)
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
            # Shrink slightly so text stays inside printed boxes.
            inset = rect + (2, 2, -2, -2)
            if inset.width < 8 or inset.height < 8:
                inset = rect
            ok = _fit_textbox(page, inset, answer_text)
            if not ok:
                overflow_ids.append(qid)

        if unresolved_ids or overflow_ids:
            failed = sorted(set(unresolved_ids + overflow_ids))
            parts = []
            if unresolved_ids:
                parts.append(f"unresolved regions for questions {sorted(set(unresolved_ids))}")
            if overflow_ids:
                parts.append(f"overflow for questions {sorted(set(overflow_ids))}")
            raise LayoutExportError("; ".join(parts), failed)

        return doc.tobytes(deflate=True, garbage=3)
    finally:
        doc.close()
