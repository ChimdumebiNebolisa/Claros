"""
PDF question extraction for Claros with page geometry and answer-region detection.

Handles PDFs where questions are on lines starting with "Question 1:", "Question 2:",
etc., or with "1.", "2)", "3.", etc. Image-only pages are marked requires_ocr and are
not collapsed into a fake question. Text documents without question markers still fall
back to a single block (id=0) for backward compatibility.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

import config
from ocr_adapter import get_ocr_adapter
from parser_layout import (
    LayoutQuestion,
    PageGeometry,
    detect_layout_questions,
    extract_page_geometry,
    filter_header_footer_lines,
)

logger = logging.getLogger(__name__)


@dataclass
class Question:
    id: int
    text: str
    page_index: int | None = None
    question_bbox: list[float] | None = None
    answer_bbox: list[float] | None = None
    layout_confidence: str | None = None
    layout_warnings: list[str] | None = None


@dataclass
class ParseResult:
    title: str
    questions: List[Question]
    pages: list[dict]
    warnings: list[str]
    parse_status: str


class PDFProcessingError(ValueError):
    """Raised for malformed or resource-exhausting PDF input."""


# Conservative Unicode to ASCII substitutions for worksheet text (math-friendly).
_UNICODE_REPLACEMENTS = (
    ("\u2212", "-"),  # minus sign
    ("\u2013", "-"),  # en dash
    ("\u2014", "-"),  # em dash
    ("\u2018", "'"),  # left single quotation mark
    ("\u2019", "'"),  # right single quotation mark
    ("\u201c", '"'),  # left double quotation mark
    ("\u201d", '"'),  # right double quotation mark
    ("\u00a0", " "),  # no-break space
)


def normalize_worksheet_text(text: str) -> str:
    """Normalize common Unicode punctuation to ASCII for safe parsing, logging, and export."""
    if not text:
        return text
    s = text
    for src, dst in _UNICODE_REPLACEMENTS:
        s = s.replace(src, dst)
    return s


def _layout_to_question(item: LayoutQuestion) -> Question:
    return Question(
        id=item.id,
        text=normalize_worksheet_text(item.text),
        page_index=item.page_index,
        question_bbox=list(item.question_bbox) if item.question_bbox else None,
        answer_bbox=list(item.answer_bbox) if item.answer_bbox else None,
        layout_confidence=item.layout_confidence,
        layout_warnings=list(item.layout_warnings),
    )


def _pages_payload(pages: list[PageGeometry]) -> list[dict]:
    return [
        {
            "page_index": page.page_index,
            "width_points": page.width,
            "height_points": page.height,
            "has_usable_text": page.has_usable_text,
            "requires_ocr": page.requires_ocr,
        }
        for page in pages
    ]


def _collect_parse_warnings(questions: List[Question], pages: list[PageGeometry], extra: list[str]) -> list[str]:
    warnings = list(extra)
    if not questions and not any(p.requires_ocr for p in pages):
        warnings.append("no_questions_detected")
    elif len(questions) == 1 and questions[0].id == 0:
        warnings.append("fallback_single_block")
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        warnings.append("duplicate_question_ids")
    if not any(p.lines for p in pages) and not any(p.requires_ocr for p in pages):
        warnings.append("empty_extraction")
    if any(p.requires_ocr for p in pages):
        warnings.append("requires_ocr")
    # Preserve deterministic unique order
    return list(dict.fromkeys(warnings))


def parse_pdf_layout(
    pdf_path: str | Path,
    *,
    apply_layout_filters: bool = True,
) -> ParseResult:
    """Parse PDF into title, questions with regions, and page metadata."""
    path = Path(pdf_path)
    try:
        doc = fitz.open(path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise PDFProcessingError("PDF could not be opened") from exc
    try:
        if doc.page_count > config.MAX_PDF_PAGES:
            raise PDFProcessingError("PDF exceeds the maximum page count")

        pages: list[PageGeometry] = []
        for index, page in enumerate(doc):
            geometry = extract_page_geometry(page, index)
            if apply_layout_filters and geometry.lines:
                # Header/footer filtering is applied during detection; keep full line list
                # here so page OCR/text flags remain accurate.
                pass
            if geometry.requires_ocr and config.ENABLE_OCR:
                adapter = get_ocr_adapter()
                ocr_result = adapter.extract_page_text(path.read_bytes(), index)
                # Boundary only: null adapter yields no blocks in this PR.
                if ocr_result.blocks:
                    geometry.requires_ocr = False
                    geometry.has_usable_text = True
            pages.append(geometry)

        full_text = "\n".join(line.text for page in pages for line in page.lines).strip()
        if full_text and len(full_text) > config.MAX_EXTRACTED_TEXT_CHARS:
            raise PDFProcessingError("PDF contains too much extracted text")

        title_source = next((line.text for page in pages for line in page.lines), path.stem)
        title = normalize_worksheet_text(title_source.strip()[:80] if title_source else path.stem)

        layout_questions, detect_warnings, parse_status = detect_layout_questions(pages)
        questions = [_layout_to_question(q) for q in layout_questions]
        warnings = _collect_parse_warnings(questions, pages, detect_warnings)

        if parse_status == "requires_ocr":
            logger.info("[parser] OCR-required worksheet with no usable text pages=%s", len(pages))
        elif parse_status == "fallback_single_block":
            logger.warning("[parser] No question lines found. fallback 1 question (id=0)")
        else:
            logger.info(
                "[parser] num_questions=%s question_ids=%s pages=%s",
                len(questions),
                [q.id for q in questions],
                len(pages),
            )

        # Keep apply_layout_filters exercised for legacy path parity in diagnostics.
        if apply_layout_filters:
            sized = [(line.text, line.size) for page in pages for line in page.lines]
            _ = filter_header_footer_lines(sized)

        return ParseResult(
            title=title,
            questions=questions,
            pages=_pages_payload(pages),
            warnings=warnings,
            parse_status=parse_status,
        )
    finally:
        doc.close()


def parse_pdf_with_diagnostics(
    pdf_path: str | Path,
    *,
    apply_layout_filters: bool = True,
) -> tuple[str, List[Question], list[str], str]:
    """
    Parse PDF and return (title, questions, warnings, parse_status).
    parse_status is one of: ok, fallback_single_block, empty_extraction, requires_ocr.
    """
    result = parse_pdf_layout(pdf_path, apply_layout_filters=apply_layout_filters)
    return result.title, result.questions, result.warnings, result.parse_status


def parse_pdf(pdf_path: str | Path) -> tuple[str, List[Question]]:
    """
    Parse PDF and extract questions. Tries (1) "Question N:" lines, then (2) "1.", "2)", "3." lines.
    Returns (title, questions). Title is the first line.
    """
    title, questions, _warnings, _status = parse_pdf_with_diagnostics(pdf_path)
    return title, questions


def questions_to_manifest_payload(questions: List[Question]) -> list[dict]:
    payload = []
    for q in questions:
        item = {
            "id": q.id,
            "text": q.text,
            "page_index": q.page_index,
            "question_bbox": q.question_bbox,
            "answer_bbox": q.answer_bbox,
            "layout_confidence": q.layout_confidence,
            "layout_warnings": list(q.layout_warnings or []),
        }
        payload.append(item)
    return payload
