"""
PDF export for Claros.

Primary path: place answers onto the original worksheet PDF using layout regions.
Legacy path: reconstruct a ReportLab PDF for manifests without layout metadata.
"""
from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from io import BytesIO
from typing import List

import fitz
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Preformatted

from manifest import validate_bbox_within_page
from parser import normalize_worksheet_text

_MIN_FONT_SIZE = 7.0
_MAX_FONT_SIZE = 12.0
_ANSWER_FONT_NAME = "ClarosUnicode"


class LayoutExportError(ValueError):
    """Raised when one or more answers cannot be placed into their regions."""

    def __init__(self, message: str, question_ids: list[int]):
        super().__init__(message)
        self.question_ids = question_ids


class SidePanelOverflowError(ValueError):
    """Raised only when a confirmed answer cannot be rendered without loss."""

    def __init__(self, affected_task_ids: list[str]):
        super().__init__("Confirmed answer could not be rendered in the side panel")
        self.affected_task_ids = affected_task_ids


class UnsupportedAnswerTextError(ValueError):
    """Raised when a confirmed answer cannot be rendered without substitution."""

    def __init__(self, affected_question_ids: list[int]):
        super().__init__("Confirmed answer contains text the PDF renderer cannot preserve")
        self.affected_question_ids = affected_question_ids


@lru_cache(maxsize=1)
def _answer_font() -> fitz.Font:
    """Use MuPDF's bundled Unicode fallback so PDF export preserves approved text."""
    return fitz.Font(fontname="cjk")


def _install_answer_font(page: fitz.Page) -> str:
    page.insert_font(fontname=_ANSWER_FONT_NAME, fontbuffer=_answer_font().buffer)
    return _ANSWER_FONT_NAME


def _validated_answer_by_id(answers: list[dict]) -> dict[int, str]:
    result: dict[int, str] = {}
    unsupported_question_ids: list[int] = []
    font = _answer_font()
    for item in answers:
        question_id = int(item["question_id"])
        answer_text = item.get("answer_text", "")
        if not isinstance(answer_text, str):
            raise TypeError("answer_text must be a string")
        if any(
            character in {"\r", "\t"} or (character != "\n" and font.has_glyph(ord(character)) == 0)
            for character in answer_text
        ):
            unsupported_question_ids.append(question_id)
        result[question_id] = answer_text
    if unsupported_question_ids:
        raise UnsupportedAnswerTextError(sorted(set(unsupported_question_ids)))
    return result


def _register_reportlab_answer_font() -> str:
    if _ANSWER_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_ANSWER_FONT_NAME, BytesIO(_answer_font().buffer)))
    return _ANSWER_FONT_NAME


def _valid_normalized_region(region: dict | None) -> bool:
    if not isinstance(region, dict):
        return False
    try:
        x, y, width, height = (float(region[key]) for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError):
        return False
    return x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= 1 and y + height <= 1


def build_original_export_pdf(
    pdf_bytes: bytes,
    questions: List[dict],
    answers: List[dict],
) -> bytes:
    """Write approved regions and append side-panel answers without guessing coordinates."""
    answer_by_id = _validated_answer_by_id(answers)
    region_by_id = {
        item["question_id"]: item.get("answer_region")
        for item in answers
        if item.get("answer_region")
    }
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    side_panel_items: list[tuple[str, str, str]] = []
    try:
        for question in questions:
            answer = answer_by_id.get(question.get("id"), "")
            explicit_region = region_by_id.get(question.get("id"))
            approved_manifest_region = (
                question.get("answer_region")
                if question.get("needs_layout_review") is not True
                else None
            )
            region = explicit_region or approved_manifest_region
            page_number = int(question.get("page", 1)) - 1
            if not answer:
                continue
            if (
                not _valid_normalized_region(region)
                or page_number < 0
                or page_number >= document.page_count
            ):
                side_panel_items.append(
                    (
                        str(question.get("label") or question.get("id")),
                        normalize_worksheet_text(question.get("text") or ""),
                        answer,
                    )
                )
                continue
            page = document[page_number]
            answer_font_name = _install_answer_font(page)
            rect = fitz.Rect(
                float(region["x"]) * page.rect.width,
                float(region["y"]) * page.rect.height,
                float(region["x"] + region["width"]) * page.rect.width,
                float(region["y"] + region["height"]) * page.rect.height,
            )
            font_size = max(8.0, min(12.0, rect.height * 0.36))
            inset = rect + (3, 2, -3, -2)
            if not _textbox_fits(
                page.rect.width,
                page.rect.height,
                inset,
                answer,
                font_size,
                answer_font_name,
            ):
                side_panel_items.append(
                    (
                        str(question.get("label") or question.get("id")),
                        normalize_worksheet_text(question.get("text") or ""),
                        answer,
                    )
                )
                continue
            page.draw_rect(rect, color=None, fill=(1, 1, 1), fill_opacity=0.94, overlay=True)
            result = page.insert_textbox(
                inset,
                answer,
                fontname=answer_font_name,
                fontsize=font_size,
                color=(0.09, 0.07, 0.05),
                lineheight=1.2,
                overlay=True,
            )
            if result < 0:
                side_panel_items.append(
                    (
                        str(question.get("label") or question.get("id")),
                        normalize_worksheet_text(question.get("text") or ""),
                        answer,
                    )
                )
        if side_panel_items:
            _append_side_panel_pages(document, side_panel_items)
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()


def _append_side_panel_pages(document: fitz.Document, items: list[tuple[str, str, str]]) -> None:
    """Append complete confirmed answers, paginating conservatively when needed."""

    def new_page():
        page = document.new_page(width=612, height=792)
        page.insert_text((54, 54), "Claros confirmed answers (side panel)", fontname="helv", fontsize=16)
        page.insert_text(
            (54, 76),
            "Original worksheet pages are preserved; these answers had no approved writable region.",
            fontname="helv",
            fontsize=9,
        )
        return page

    def chunks(text: str, size: int = 400) -> list[str]:
        remaining = text
        result: list[str] = []
        while remaining:
            if len(remaining) <= size:
                result.append(remaining)
                break
            split = remaining.rfind(" ", 0, size + 1)
            if split <= 0:
                split = size
            result.append(remaining[:split])
            remaining = remaining[split:]
        return result or [""]

    for label, prompt, answer in items:
        prompt = prompt.replace("\n", " ")[:280]
        for index, chunk in enumerate(chunks(answer)):
            page = new_page()
            answer_font_name = _install_answer_font(page)
            heading = f"Question {label}: {prompt}" if index == 0 else f"Question {label} (continued)"
            heading_result = page.insert_textbox(
                fitz.Rect(54, 104, page.rect.width - 54, 146),
                heading,
                fontname=answer_font_name,
                fontsize=10,
            )
            answer_result = page.insert_textbox(
                fitz.Rect(54, 150, page.rect.width - 54, page.rect.height - 54),
                chunk,
                fontname=answer_font_name,
                fontsize=10,
                lineheight=1.25,
            )
            if heading_result < 0 or answer_result < 0:
                raise SidePanelOverflowError([label])


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
    body_style = ParagraphStyle("AnswerBody", parent=styles["Normal"], fontName=_register_reportlab_answer_font())

    story = []
    story.append(Paragraph("Claros - Assignment Answers", title_style))
    safe_title = normalize_worksheet_text(title)
    story.append(Paragraph(safe_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), body_style))
    story.append(Spacer(1, 0.25 * inch))

    answer_by_id = _validated_answer_by_id(answers)

    for q in questions:
        qid = q.get("id", 0)
        qtext = normalize_worksheet_text(q.get("text") or "")
        qtext = qtext.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(f"<b>Question {qid}</b>: {qtext}", heading_style))
        answer_text = answer_by_id.get(qid) or "(No answer)"
        story.append(Preformatted(answer_text, body_style))
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
        try:
            bbox = validate_bbox_within_page(
                override["answer_bbox"],
                page_width=float(page["width_points"]),
                page_height=float(page["height_points"]),
                label=f"layout_overrides question {qid}",
            )
        except ValueError as exc:
            raise LayoutExportError(str(exc), [qid]) from exc
        return page_index, bbox

    bbox = question.get("answer_bbox")
    page_index = question.get("page_index")
    if bbox is None or page_index is None:
        return None
    page = pages_by_index.get(int(page_index))
    if page is None:
        return None
    try:
        validated = validate_bbox_within_page(
            bbox,
            page_width=float(page["width_points"]),
            page_height=float(page["height_points"]),
            label=f"answer_bbox question {qid}",
        )
    except ValueError as exc:
        raise LayoutExportError(str(exc), [qid]) from exc
    return int(page_index), validated


def _textbox_fits(
    page_width: float,
    page_height: float,
    rect: fitz.Rect,
    text: str,
    fontsize: float,
    fontname: str,
) -> bool:
    """Probe fit on a scratch page so failed attempts never touch the original."""
    probe = fitz.open()
    try:
        scratch = probe.new_page(width=page_width, height=page_height)
        _install_answer_font(scratch)
        rc = scratch.insert_textbox(
            rect,
            text,
            fontname=fontname,
            fontsize=fontsize,
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0, 0, 0),
        )
        return rc >= 0
    finally:
        probe.close()


def _fit_textbox(page, rect: fitz.Rect, text: str, fontname: str) -> bool:
    """Insert multiline text into rect, shrinking font until it fits. Returns False on overflow."""
    fontsize = _MAX_FONT_SIZE
    chosen = None
    while fontsize >= _MIN_FONT_SIZE:
        if _textbox_fits(page.rect.width, page.rect.height, rect, text, fontsize, fontname):
            chosen = fontsize
            break
        fontsize -= 0.5
    if chosen is None:
        return False
    rc = page.insert_textbox(
        rect,
        text,
        fontname=fontname,
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
    answer_by_id = _validated_answer_by_id(answers)

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
            answer_font_name = _install_answer_font(page)
            rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
            # Shrink slightly so text stays inside printed boxes.
            inset = rect + (2, 2, -2, -2)
            if inset.width < 8 or inset.height < 8:
                inset = rect
            ok = _fit_textbox(page, inset, answer_text, answer_font_name)
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
