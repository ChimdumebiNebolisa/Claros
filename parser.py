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

from parser_layout import filter_header_footer_lines

logger = logging.getLogger(__name__)

@dataclass
class Question:
    id: int
    text: str


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
        Question(id=q.id, text=normalize_worksheet_text(q.text)) for q in questions
    ]
    return norm_title, norm_questions


def _extract_lines_with_size(doc: fitz.Document) -> List[tuple[str, float]]:
    """Extract (line_text, font_size) for each line from PDF. Uses first span size per line."""
    lines: List[tuple[str, float]] = []
    for page in doc:
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
                        lines.append((text, line_size if line_size is not None else 0.0))
    return lines


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
    doc = fitz.open(path)
    try:
        lines_with_size = _extract_lines_with_size(doc)
        if apply_layout_filters:
            lines_with_size = filter_header_footer_lines(lines_with_size)
        lines = [t for t, _ in lines_with_size]
        full_text = "\n".join(lines).strip() or "(No extractable text)"

        if not lines:
            title = path.stem
            questions = [Question(id=0, text=full_text)]
            warnings = _collect_parse_warnings(questions, lines)
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
            warnings = _collect_parse_warnings(questions, lines)
            logger.warning("[parser] No question lines found. fallback 1 question (id=0)")
            return _normalize_parse_result(title, questions) + (warnings, "fallback_single_block")

        warnings = _collect_parse_warnings(questions, lines)
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
