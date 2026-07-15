"""
PDF question extraction for Claros. Handles PDFs where questions are on lines
starting with "Question 1:", "Question 2:", etc., or with "1.", "2)", "3.", etc.
Falls back to full text as single block (id=0) only if no question lines found.
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

import config
from parser_layout import filter_header_footer_lines

logger = logging.getLogger(__name__)

@dataclass
class Question:
    id: int
    text: str
    page: int = 1
    prompt_region: dict[str, float] | None = None
    answer_region: dict[str, float] | None = None
    detected_answer_region: dict[str, float] | None = None
    layout_confidence: float = 0.0
    needs_layout_review: bool = True


class PDFProcessingError(ValueError):
    """Raised for malformed or resource-exhausting PDF input."""


# Line starting with "Question N:" or "Question N." (case insensitive). Captures N and rest of line.
_QUESTION_LINE_RE = re.compile(r"^\s*Question\s*(\d+)\s*[:.]\s*(.*)", re.IGNORECASE)

# Line starting with "N." or "N)" (numbered list) for worksheet-style PDFs. Captures N and rest of line.
_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)[.)]\s*(.*)")

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


def _normalize_parse_result(title: str, questions: List[Question]) -> tuple[str, List[Question]]:
    norm_title = normalize_worksheet_text(title)
    norm_questions = [
        Question(
            id=q.id,
            text=normalize_worksheet_text(q.text),
            page=q.page,
            prompt_region=q.prompt_region,
            answer_region=q.answer_region,
            detected_answer_region=q.detected_answer_region,
            layout_confidence=q.layout_confidence,
            needs_layout_review=q.needs_layout_review,
        )
        for q in questions
    ]
    return norm_title, norm_questions


def _extract_line_records(doc: fitz.Document) -> list[dict]:
    """Extract text, size, page and geometry for every readable PDF line."""
    records: list[dict] = []
    for page_index, page in enumerate(doc):
        block_dict = page.get_text("dict", sort=True)
        for block in block_dict.get("blocks", []):
            for line in block.get("lines", []):
                line_text_parts = []
                line_size = None
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if text:
                        line_text_parts.append(text)
                        if line_size is None and "size" in span:
                            line_size = span["size"]
                if line_text_parts:
                    text = " ".join(line_text_parts).strip()
                    if text:
                        records.append(
                            {
                                "text": text,
                                "size": line_size if line_size is not None else 0.0,
                                "page": page_index + 1,
                                "bbox": tuple(line.get("bbox", (0, 0, 0, 0))),
                                "page_width": float(page.rect.width),
                                "page_height": float(page.rect.height),
                            }
                        )
    return records


def _extract_lines_with_size(doc: fitz.Document) -> List[tuple[str, float]]:
    """Extract (line_text, font_size) for each line from PDF."""
    return [(record["text"], record["size"]) for record in _extract_line_records(doc)]


def _normalized_region(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    page_width: float,
    page_height: float,
) -> dict[str, float]:
    x0 = max(0.0, min(x0, page_width))
    y0 = max(0.0, min(y0, page_height))
    x1 = max(x0 + 1.0, min(x1, page_width))
    y1 = max(y0 + 1.0, min(y1, page_height))
    return {
        "x": round(x0 / page_width, 6),
        "y": round(y0 / page_height, 6),
        "width": round((x1 - x0) / page_width, 6),
        "height": round((y1 - y0) / page_height, 6),
    }


def _attach_question_layout(doc: fitz.Document, questions: List[Question]) -> None:
    """Attach conservative, normalized prompt and answer regions to parsed questions."""
    records = _extract_line_records(doc)
    starts: list[tuple[int, int]] = []
    for index, record in enumerate(records):
        match = _QUESTION_LINE_RE.match(record["text"]) or _NUMBERED_LINE_RE.match(record["text"])
        if match:
            starts.append((index, int(match.group(1))))

    for start_position, (record_index, question_id) in enumerate(starts):
        question = next((item for item in questions if item.id == question_id), None)
        if question is None:
            continue
        start = records[record_index]
        next_index = starts[start_position + 1][0] if start_position + 1 < len(starts) else len(records)
        segment = [
            record
            for record in records[record_index:next_index]
            if record["page"] == start["page"]
        ]
        x0, y0, x1, y1 = start["bbox"]
        prompt_bottom = max((record["bbox"][3] for record in segment), default=y1)
        question.page = start["page"]
        question.prompt_region = _normalized_region(
            x0 - 4,
            y0 - 4,
            max(x1 + 12, start["page_width"] - 42),
            prompt_bottom + 4,
            start["page_width"],
            start["page_height"],
        )

        candidate = next((record for record in segment[1:] if "_" in record["text"]), None)
        if candidate is None:
            candidate = next(
                (
                    record
                    for record in segment[1:]
                    if re.search(
                        r"\b(answer|response|width|length|student tickets|adult tickets)\s*[:=]",
                        record["text"],
                        re.I,
                    )
                ),
                None,
            )
        confidence = 0.0
        if candidate is not None:
            cx0, cy0, cx1, cy1 = candidate["bbox"]
            first_blank = candidate["text"].find("_")
            if first_blank >= 0:
                text_length = max(1, len(candidate["text"]))
                cx0 = cx0 + ((cx1 - cx0) * first_blank / text_length) - 8
                confidence = 0.98
            else:
                cx0 = min(cx0 + (cx1 - cx0) * 0.45, cx1 - 72)
                confidence = 0.72
            region = _normalized_region(
                cx0,
                cy0 - 4,
                max(cx1 + 80, cx0 + 150),
                cy1 + 18,
                candidate["page_width"],
                candidate["page_height"],
            )
        else:
            region = _normalized_region(
                x0,
                prompt_bottom + 8,
                start["page_width"] - 42,
                prompt_bottom + 54,
                start["page_width"],
                start["page_height"],
            )
            confidence = 0.35
        question.answer_region = region
        question.detected_answer_region = dict(region)
        question.layout_confidence = confidence
        question.needs_layout_review = confidence < 0.7


def _collect_parse_warnings(questions: List[Question], lines: List[str]) -> list[str]:
    warnings: list[str] = []
    if not questions:
        warnings.append("no_questions_detected")
    elif len(questions) == 1 and questions[0].id == 0:
        warnings.append("fallback_single_block")
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        warnings.append("duplicate_question_ids")
    if not lines:
        warnings.append("empty_extraction")
    return warnings


def parse_pdf_with_diagnostics(
    pdf_path: str | Path,
    *,
    apply_layout_filters: bool = True,
) -> tuple[str, List[Question], list[str], str]:
    """
    Parse PDF and return (title, questions, warnings, parse_status).
    parse_status is one of: ok, fallback_single_block, empty_extraction.
    """
    path = Path(pdf_path)
    try:
        doc = fitz.open(path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise PDFProcessingError("PDF could not be opened") from exc
    try:
        if doc.page_count > config.MAX_PDF_PAGES:
            raise PDFProcessingError("PDF exceeds the maximum page count")
        lines_with_size = _extract_lines_with_size(doc)
        if apply_layout_filters:
            lines_with_size = filter_header_footer_lines(lines_with_size)
        lines = [t for t, _ in lines_with_size]
        full_text = "\n".join(lines).strip() or "(No extractable text)"
        if len(full_text) > config.MAX_EXTRACTED_TEXT_CHARS:
            raise PDFProcessingError("PDF contains too much extracted text")

        if not lines:
            title = path.stem
            questions = [Question(id=0, text=full_text)]
            _attach_question_layout(doc, questions)
            warnings = _collect_parse_warnings(questions, lines)
            warnings.append("layout_review_required")
            return _normalize_parse_result(title, questions) + (warnings, "empty_extraction")

        title = lines[0].strip()[:80] if lines else path.stem
        questions: List[Question] = []
        i = 0

        while i < len(lines):
            m = _QUESTION_LINE_RE.match(lines[i])
            if m:
                qid = int(m.group(1))
                text_parts = [m.group(2).strip()] if m.group(2).strip() else []
                i += 1
                while i < len(lines) and not _QUESTION_LINE_RE.match(lines[i]):
                    text_parts.append(lines[i])
                    i += 1
                q_text = "\n".join(text_parts).strip()
                questions.append(Question(id=qid, text=q_text))
            else:
                i += 1

        if not questions:
            i = 0
            while i < len(lines):
                m = _NUMBERED_LINE_RE.match(lines[i])
                if m:
                    qid = int(m.group(1))
                    text_parts = [m.group(2).strip()] if m.group(2).strip() else []
                    i += 1
                    while i < len(lines) and not _NUMBERED_LINE_RE.match(lines[i]):
                        text_parts.append(lines[i])
                        i += 1
                    q_text = "\n".join(text_parts).strip()
                    if q_text or qid <= 10:
                        questions.append(Question(id=qid, text=q_text or f"Question {qid}"))
                else:
                    i += 1

        if not questions:
            questions = [Question(id=0, text=full_text)]
            _attach_question_layout(doc, questions)
            warnings = _collect_parse_warnings(questions, lines)
            warnings.append("layout_review_required")
            logger.warning("[parser] No question lines found. fallback 1 question (id=0)")
            return _normalize_parse_result(title, questions) + (warnings, "fallback_single_block")

        _attach_question_layout(doc, questions)
        warnings = _collect_parse_warnings(questions, lines)
        if any(question.needs_layout_review for question in questions):
            warnings.append("layout_review_required")
        question_ids = [q.id for q in questions]
        logger.info(
            "[parser] num_questions=%s question_ids=%s",
            len(questions), question_ids,
        )
        return _normalize_parse_result(title, questions) + (warnings, "ok")
    finally:
        doc.close()


def parse_pdf(pdf_path: str | Path) -> tuple[str, List[Question]]:
    """
    Parse PDF and extract questions. Tries (1) "Question N:" lines, then (2) "1.", "2)", "3." lines.
    Returns (title, questions). Title is the first line. Falls back to one question (id=0) only
    if neither pattern matches.
    """
    title, questions, _warnings, _status = parse_pdf_with_diagnostics(pdf_path)
    return title, questions
