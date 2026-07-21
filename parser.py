"""Conservative PDF question extraction for clearly labeled student worksheets."""
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
    label: str | None = None
    page: int = 1
    prompt_region: dict[str, float] | None = None
    answer_region: dict[str, float] | None = None
    detected_answer_region: dict[str, float] | None = None
    layout_confidence: float = 0.0
    needs_layout_review: bool = True


class PDFProcessingError(ValueError):
    """Raised for malformed or resource-exhausting PDF input."""


# Preserve compound source labels while keeping numeric internal IDs for APIs.
_QUESTION_LINE_RE = re.compile(
    r"^\s*Question\s*(\d+[A-Za-z]?)\s*[:.)-]\s*(.*)",
    re.IGNORECASE,
)

_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+[A-Za-z]?)[.)]\s*(.*)")

_STUDENT_MARKERS = (
    "student worksheet",
    "student handout",
    "student activity",
    "student guide",
    "worksheet",
)
_EDUCATOR_MARKERS = (
    "teacher guide",
    "teacher answer",
    "answer key",
    "lesson overview",
    "teaching time",
    "teacher notes",
    "educator guide",
)
_ANSWER_KEY_MARKERS = ("answer key", "teacher answer")
_SECTION_BOUNDARIES = {
    "answer key",
    "author",
    "materials",
    "procedure",
    "reading extension",
    "references",
    "resources",
    "sources",
    "standards",
    "teacher guide",
}
_QUESTION_START_RE = re.compile(
    r"^(what|why|how|where|when|which|who|explain|describe|identify|calculate|"
    r"compare|contrast|solve|write|draw|record|complete|fill|list|determine|predict|"
    r"revise|summarize|name|analyze|evaluate)\b",
    re.IGNORECASE,
)
_PROCEDURE_START_RE = re.compile(
    r"^(add|attach|check|clean|click|copy|gather|get|log on|place|plug|put|"
    r"read|remove|repeat|review|secure|turn|use|visit|wait|watch)\b",
    re.IGNORECASE,
)
_NUMERIC_VALUE_RE = re.compile(
    r"^[\s$+-]*(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:\s*[x×]\s*10\s*\^?\s*[+-]?\d+)?\s*$",
    re.IGNORECASE,
)

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
    return "".join(ch for ch in s if ch in "\n\t" or ord(ch) >= 32)


def _normalize_parse_result(title: str, questions: List[Question]) -> tuple[str, List[Question]]:
    norm_title = normalize_worksheet_text(title)
    norm_questions = [
        Question(
            id=q.id,
            text=normalize_worksheet_text(q.text),
            label=q.label,
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


def _page_records(records: list[dict]) -> dict[int, list[dict]]:
    pages: dict[int, list[dict]] = {}
    for record in records:
        pages.setdefault(record["page"], []).append(record)
    return pages


def _classify_pages(records_by_page: dict[int, list[dict]]) -> tuple[dict[int, str], bool]:
    """Track explicit student/educator sections without guessing across section changes."""
    classes: dict[int, str] = {}
    current = "uncertain"
    saw_student = False
    saw_educator = False
    for page_number in sorted(records_by_page):
        page_text = "\n".join(record["text"] for record in records_by_page[page_number]).lower()
        has_answer_key = any(marker in page_text for marker in _ANSWER_KEY_MARKERS)
        has_student = any(marker in page_text for marker in _STUDENT_MARKERS)
        has_educator = any(marker in page_text for marker in _EDUCATOR_MARKERS)
        has_explicit_questions = any(
            _QUESTION_LINE_RE.match(record["text"]) for record in records_by_page[page_number]
        )
        if has_answer_key:
            current = "answer_key"
            saw_educator = True
        elif has_student and not has_educator:
            current = "student"
            saw_student = True
        elif has_explicit_questions and not has_educator:
            current = "student"
            saw_student = True
        elif has_educator:
            current = "educator"
            saw_educator = True
        classes[page_number] = current
    return classes, saw_student and saw_educator


def _source_match(text: str) -> tuple[str, str, bool] | None:
    explicit = _QUESTION_LINE_RE.match(text)
    if explicit:
        return explicit.group(1), explicit.group(2).strip(), True
    numbered = _NUMBERED_LINE_RE.match(text)
    if numbered:
        label = numbered.group(1)
        body = numbered.group(2).strip()
        child = re.match(r"^([A-Za-z])[.)]\s+(.*)", body)
        if child and label.isdigit():
            label += child.group(1).lower()
            body = child.group(2).strip()
        return label, body, False
    return None


def _looks_like_question(label: str, body: str, *, explicit: bool) -> bool:
    body = normalize_worksheet_text(body).strip()
    if not body or not any(ch.isalpha() for ch in body):
        return False
    number = int(re.match(r"\d+", label).group())
    if number <= 0 or number > 50:
        return False
    if _NUMERIC_VALUE_RE.fullmatch(body) or re.match(r"^(https?://|www\.)", body, re.I):
        return False
    if re.match(r"^\d+(?:[.,]\d+)?\s*[x×]\s*10", body, re.I):
        return False
    if explicit:
        return len(body.split()) >= 2
    if "?" in body or _QUESTION_START_RE.match(body):
        return True
    if re.search(r"\b(?:draw|explain|calculate|solve|describe|compare|predict|summarize)\b", body, re.I):
        return True
    if re.search(r"\b(question|prompt)\b", body, re.I):
        return True
    if _PROCEDURE_START_RE.match(body):
        return False
    return bool(re.search(r"\b(show your work|write your answer|record your answer)\b", body, re.I))


def _is_boundary(text: str) -> bool:
    normalized = normalize_worksheet_text(text).strip().lower().rstrip(":")
    return normalized in _SECTION_BOUNDARIES


def _assign_internal_ids(candidates: list[dict]) -> None:
    for internal_id, candidate in enumerate(candidates, start=1):
        candidate["id"] = internal_id


def _horizontal_answer_region(
    page: fitz.Page,
    *,
    prompt_bottom: float,
    next_question_top: float | None,
) -> tuple[dict[str, float] | None, float]:
    lines: list[fitz.Rect] = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if not item or item[0] != "l":
                continue
            p0, p1 = item[1], item[2]
            if abs(p0.y - p1.y) > 2 or abs(p1.x - p0.x) < 80:
                continue
            y = float((p0.y + p1.y) / 2)
            if y <= prompt_bottom + 4:
                continue
            if next_question_top is not None and y >= next_question_top - 4:
                continue
            lines.append(fitz.Rect(min(p0.x, p1.x), y - 5, max(p0.x, p1.x), y + 16))
    if not lines:
        return None, 0.0
    x0 = min(line.x0 for line in lines)
    x1 = max(line.x1 for line in lines)
    y0 = min(line.y0 for line in lines)
    y1 = max(line.y1 for line in lines)
    return _normalized_region(x0, y0, x1, y1, page.rect.width, page.rect.height), 0.92


def _answer_region_for_candidate(
    page: fitz.Page,
    records: list[dict],
    *,
    record_index: int,
    prompt_bottom: float,
    next_source_index: int | None,
    allow_page_end_blank: bool,
) -> tuple[dict[str, float] | None, float]:
    stop = next_source_index if next_source_index is not None else len(records)
    for index in range(record_index + 1, stop):
        if _is_boundary(records[index]["text"]):
            stop = index
            break
    next_question_top = records[next_source_index]["bbox"][1] if next_source_index is not None else None
    for record in records[record_index + 1 : stop]:
        text = normalize_worksheet_text(record["text"])
        if "_" not in text:
            continue
        x0, y0, x1, y1 = record["bbox"]
        blank_at = text.find("_")
        x0 += ((x1 - x0) * blank_at / max(1, len(text))) - 6
        region = _normalized_region(
            x0,
            y0 - 4,
            max(x1, x0 + 120),
            y1 + 18,
            record["page_width"],
            record["page_height"],
        )
        return region, 0.98

    drawn, confidence = _horizontal_answer_region(
        page,
        prompt_bottom=prompt_bottom,
        next_question_top=next_question_top,
    )
    if drawn:
        return drawn, confidence

    if next_question_top is not None:
        y0 = prompt_bottom + 6
        y1 = next_question_top - 6
        if y1 - y0 >= 36:
            start = records[record_index]
            return (
                _normalized_region(
                    max(36, start["bbox"][0]),
                    y0,
                    start["page_width"] - 36,
                    y1,
                    start["page_width"],
                    start["page_height"],
                ),
                0.82,
            )
    elif allow_page_end_blank:
        later_content = [
            record["bbox"][1]
            for record in records[record_index + 1 : stop]
            if record["bbox"][1] > prompt_bottom + 8 and "_" not in record["text"]
        ]
        y0 = prompt_bottom + 6
        y1 = (min(later_content) - 6) if later_content else (page.rect.height - 36)
        if y1 - y0 >= 36:
            start = records[record_index]
            return (
                _normalized_region(
                    max(36, start["bbox"][0]),
                    y0,
                    start["page_width"] - 36,
                    y1,
                    start["page_width"],
                    start["page_height"],
                ),
                0.82,
            )
    return None, 0.0


def _detect_page_questions(
    doc: fitz.Document,
    records_by_page: dict[int, list[dict]],
    page_classes: dict[int, str],
) -> list[dict]:
    candidates: list[dict] = []
    for page_number, records in records_by_page.items():
        if page_classes.get(page_number) != "student":
            continue
        source_positions = [index for index, record in enumerate(records) if _source_match(record["text"])]
        for position, record_index in enumerate(source_positions):
            record = records[record_index]
            matched = _source_match(record["text"])
            if matched is None:
                continue
            label, body, explicit = matched
            next_source_index = source_positions[position + 1] if position + 1 < len(source_positions) else None
            stop = next_source_index if next_source_index is not None else len(records)
            prompt_records = [record]
            text_parts = [body]
            previous_bottom = record["bbox"][3]
            for following in records[record_index + 1 : stop]:
                following_text = normalize_worksheet_text(following["text"]).strip()
                if not following_text or "_" in following_text or _is_boundary(following_text):
                    break
                if re.search(r"\b(answer|final answer|show your work)\s*:", following_text, re.I):
                    break
                if following["bbox"][1] - previous_bottom > 26:
                    break
                prompt_records.append(following)
                text_parts.append(following_text)
                previous_bottom = following["bbox"][3]
            prompt_text = "\n".join(text_parts).strip()
            if not _looks_like_question(label, prompt_text, explicit=explicit):
                continue
            x0 = min(item["bbox"][0] for item in prompt_records)
            y0 = min(item["bbox"][1] for item in prompt_records)
            x1 = max(item["bbox"][2] for item in prompt_records)
            y1 = max(item["bbox"][3] for item in prompt_records)
            prompt_region = _normalized_region(
                x0 - 4,
                y0 - 4,
                x1 + 4,
                y1 + 4,
                record["page_width"],
                record["page_height"],
            )
            answer_region, confidence = _answer_region_for_candidate(
                doc[page_number - 1],
                records,
                record_index=record_index,
                prompt_bottom=y1,
                next_source_index=next_source_index,
                allow_page_end_blank=bool(
                    re.search(
                        r"\b(?:write|draw|answer|respond)\b.*\b(?:below|space provided)\b",
                        prompt_text,
                        re.I | re.S,
                    )
                ),
            )
            if re.search(r"\b(?:fill in|complete)\s+table\b|\btable\s+\d+\b", prompt_text, re.I):
                answer_region = None
                confidence = 0.0
            candidates.append(
                {
                    "label": label,
                    "text": prompt_text,
                    "page": page_number,
                    "prompt_region": prompt_region,
                    "answer_region": answer_region,
                    "confidence": confidence,
                }
            )
    _assign_internal_ids(candidates)
    return candidates


def _select_title(records: list[dict], path: Path) -> str:
    usable = [normalize_worksheet_text(record["text"]).strip() for record in records]
    usable = [line for line in usable if len(line) >= 3 and any(ch.isalpha() for ch in line)]
    worksheet_title = next((line for line in usable[:30] if "worksheet" in line.lower()), None)
    return (worksheet_title or (usable[0] if usable else path.stem))[:80]


def parse_pdf_with_diagnostics(
    pdf_path: str | Path,
    *,
    apply_layout_filters: bool = True,
) -> tuple[str, List[Question], list[str], str]:
    """
    Parse PDF and return (title, questions, warnings, parse_status).

    Only clearly labeled student worksheet questions are accepted. Uncertain
    layouts remain available for review but never report a misleading ``ok``.
    """
    path = Path(pdf_path)
    try:
        doc = fitz.open(path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise PDFProcessingError("PDF could not be opened") from exc
    try:
        if doc.page_count > config.MAX_PDF_PAGES:
            raise PDFProcessingError("PDF exceeds the maximum page count")
        records = _extract_line_records(doc)
        lines_with_size = [(record["text"], record["size"]) for record in records]
        if apply_layout_filters:
            lines_with_size = filter_header_footer_lines(lines_with_size)
        lines = [t for t, _ in lines_with_size]
        full_text = "\n".join(lines).strip()
        if len(full_text) > config.MAX_EXTRACTED_TEXT_CHARS:
            raise PDFProcessingError("PDF contains too much extracted text")

        title = _select_title(records, path)
        if not lines:
            return title, [], ["requires_ocr"], "requires_ocr"

        records_by_page = _page_records(records)
        page_classes, mixed_packet = _classify_pages(records_by_page)
        candidates = _detect_page_questions(doc, records_by_page, page_classes)
        questions = [
            Question(
                id=candidate["id"],
                label=candidate["label"],
                text=candidate["text"],
                page=candidate["page"],
                prompt_region=candidate["prompt_region"],
                answer_region=candidate["answer_region"],
                detected_answer_region=(
                    dict(candidate["answer_region"]) if candidate["answer_region"] else None
                ),
                layout_confidence=candidate["confidence"],
                needs_layout_review=candidate["confidence"] < 0.7,
            )
            for candidate in candidates
        ]
        if not questions:
            warnings = ["no_questions_detected", "unsupported_layout"]
            if not any(value == "student" for value in page_classes.values()):
                warnings.append("student_page_not_identified")
            if mixed_packet:
                warnings.append("mixed_educator_student_packet")
            return title, [], warnings, "unsupported_layout"

        warnings: list[str] = []
        labels = [question.label for question in questions]
        if len(labels) != len(set(labels)):
            warnings.append("repeated_question_labels")
        numeric_labels = [int(label) for label in labels if label and label.isdigit()]
        if len(numeric_labels) >= 2 and numeric_labels != sorted(numeric_labels):
            warnings.append("nonsequential_question_labels")
        if mixed_packet:
            warnings.append("mixed_educator_student_packet")
        if any(value in {"uncertain", "educator", "answer_key"} for value in page_classes.values()):
            warnings.append("non_student_pages_excluded")
        if any(question.needs_layout_review for question in questions):
            warnings.append("unresolved_answer_regions")

        needs_review = bool(warnings)
        status = "layout_review_required" if needs_review else "ok"
        if needs_review:
            warnings.append("layout_review_required")
            for question in questions:
                question.needs_layout_review = True
        question_ids = [q.id for q in questions]
        logger.info(
            "[parser] num_questions=%s question_ids=%s parse_status=%s",
            len(questions), question_ids, status,
        )
        return _normalize_parse_result(title, questions) + (list(dict.fromkeys(warnings)), status)
    finally:
        doc.close()


def parse_pdf(pdf_path: str | Path) -> tuple[str, List[Question]]:
    """
    Parse a supported student worksheet and return its title and questions.

    Unsupported and OCR-required inputs return an empty question list; callers
    that need the reason should use :func:`parse_pdf_with_diagnostics`.
    """
    title, questions, _warnings, _status = parse_pdf_with_diagnostics(pdf_path)
    return title, questions
