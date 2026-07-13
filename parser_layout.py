"""Layout heuristics and geometry extraction for worksheet PDF parsing.

Coordinates use PDF points with origin at the top-left of each page
(PyMuPDF page space). Rectangles are [x0, y0, x1, y1].
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

from manifest import MIN_ANSWER_HEIGHT, MIN_ANSWER_WIDTH, LayoutConfidence

_QUESTION_LINE_RE = re.compile(r"^\s*Question\s*(\d+)\s*[:.]\s*(.*)", re.IGNORECASE)
_NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)[.)]\s*(.*)")

LayoutConfidenceValue = LayoutConfidence


@dataclass
class TextSpan:
    text: str
    bbox: tuple[float, float, float, float]
    size: float
    page_index: int


@dataclass
class TextLine:
    text: str
    bbox: tuple[float, float, float, float]
    size: float
    page_index: int
    spans: list[TextSpan] = field(default_factory=list)


@dataclass
class PageGeometry:
    page_index: int
    width: float
    height: float
    lines: list[TextLine]
    has_usable_text: bool
    requires_ocr: bool


@dataclass
class LayoutQuestion:
    id: int
    text: str
    page_index: int | None
    question_bbox: list[float] | None
    answer_bbox: list[float] | None
    layout_confidence: LayoutConfidenceValue | None
    layout_warnings: list[str] = field(default_factory=list)


def median_body_font_size(lines_with_size: list[tuple[str, float]]) -> float:
    sizes = [s for _, s in lines_with_size if s > 0]
    if not sizes:
        return 0.0
    return float(median(sizes))


def is_likely_header_footer(
    line: str,
    font_size: float,
    body_size: float,
    *,
    y0: float | None = None,
    page_height: float | None = None,
) -> bool:
    if not line.strip():
        return True
    lower = line.strip().lower()
    if lower.isdigit() and len(lower) <= 3:
        return True
    # Only treat standalone page markers as footers (not "First page item").
    if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", lower):
        return True
    # Size heuristic only near page edges so mid-page small text is preserved.
    near_edge = True
    if y0 is not None and page_height and page_height > 0:
        near_edge = y0 <= page_height * 0.08 or y0 >= page_height * 0.92
    if (
        near_edge
        and body_size > 0
        and font_size > 0
        and font_size < body_size * 0.85
    ):
        return True
    return False


def filter_header_footer_lines(lines_with_size: list[tuple[str, float]]) -> list[tuple[str, float]]:
    body = median_body_font_size(lines_with_size)
    return [
        (text, size)
        for text, size in lines_with_size
        if not is_likely_header_footer(text, size, body)
    ]


def filter_header_footer_text_lines(lines: list[TextLine], page_height: float | None = None) -> list[TextLine]:
    sized = [(line.text, line.size) for line in lines]
    body = median_body_font_size(sized)
    height = page_height
    if height is None and lines:
        height = max(line.bbox[3] for line in lines) + 36.0
    return [
        line
        for line in lines
        if not is_likely_header_footer(
            line.text,
            line.size,
            body,
            y0=line.bbox[1],
            page_height=height,
        )
    ]


def union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float] | None:
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return (x0, y0, x1, y1)


def bbox_list(box: tuple[float, float, float, float] | None) -> list[float] | None:
    if box is None:
        return None
    return [float(box[0]), float(box[1]), float(box[2]), float(box[3])]


def page_has_usable_text(page) -> bool:
    """Heuristic: enough extractable characters to support text-layout parsing."""
    try:
        text = (page.get_text("text") or "").strip()
    except Exception:
        return False
    alnum = sum(1 for ch in text if ch.isalnum())
    return alnum >= 12


def extract_page_geometry(page, page_index: int, *, usable_text_min: int = 12) -> PageGeometry:
    width = float(page.rect.width)
    height = float(page.rect.height)
    lines: list[TextLine] = []
    try:
        block_dict = page.get_text("dict", sort=False)
    except Exception:
        block_dict = {"blocks": []}

    for block in block_dict.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans: list[TextSpan] = []
            text_parts: list[str] = []
            line_size = 0.0
            for span in line.get("spans", []):
                text = (span.get("text") or "").replace("\x00", "")
                if not text.strip() and not text:
                    continue
                bbox = tuple(float(v) for v in span.get("bbox", (0, 0, 0, 0)))
                size = float(span.get("size") or 0.0)
                spans.append(TextSpan(text=text, bbox=bbox, size=size, page_index=page_index))
                if text.strip():
                    text_parts.append(text)
                    if line_size <= 0 and size > 0:
                        line_size = size
            if not text_parts:
                continue
            line_text = " ".join(part.strip() for part in text_parts if part.strip()).strip()
            if not line_text:
                continue
            line_bbox = union_bbox([s.bbox for s in spans]) or tuple(float(v) for v in line.get("bbox", (0, 0, 0, 0)))
            lines.append(
                TextLine(
                    text=line_text,
                    bbox=line_bbox,
                    size=line_size,
                    page_index=page_index,
                    spans=spans,
                )
            )

    alnum = sum(1 for line in lines for ch in line.text if ch.isalnum())
    has_usable = alnum >= usable_text_min
    return PageGeometry(
        page_index=page_index,
        width=width,
        height=height,
        lines=lines,
        has_usable_text=has_usable,
        requires_ocr=not has_usable,
    )


def _match_question_label(text: str) -> tuple[str, int, str] | None:
    m = _QUESTION_LINE_RE.match(text)
    if m:
        return ("question", int(m.group(1)), (m.group(2) or "").strip())
    m = _NUMBERED_LINE_RE.match(text)
    if m:
        return ("numbered", int(m.group(1)), (m.group(2) or "").strip())
    return None


def _column_key(line: TextLine, page_width: float) -> int:
    """Bucket lines into columns using left-edge position."""
    mid = page_width / 2.0
    # Leave a small center band; prefer explicit left/right when clear.
    if line.bbox[0] >= mid - 18:
        return 1
    return 0


def _sort_reading_order(lines: list[TextLine], page_width: float) -> list[TextLine]:
    """Sort by column then top-to-bottom. Safer than PyMuPDF sort=True for two columns."""
    return sorted(
        lines,
        key=lambda line: (_column_key(line, page_width), line.bbox[1], line.bbox[0]),
    )


def _same_column(a: TextLine, b: TextLine, page_width: float) -> bool:
    return _column_key(a, page_width) == _column_key(b, page_width)


def page_has_multiple_columns(lines: list[TextLine], page_width: float) -> bool:
    if not lines:
        return False
    left = sum(1 for line in lines if _column_key(line, page_width) == 0)
    right = sum(1 for line in lines if _column_key(line, page_width) == 1)
    return left >= 2 and right >= 2


def _propose_answer_bbox(
    *,
    question_lines: list[TextLine],
    next_question_line: TextLine | None,
    page: PageGeometry,
) -> tuple[list[float] | None, list[str], LayoutConfidenceValue]:
    warnings: list[str] = []
    q_box = union_bbox([line.bbox for line in question_lines])
    if q_box is None:
        return None, ["missing_question_geometry"], "low"

    multi_col = page_has_multiple_columns(page.lines, page.width)
    x0 = max(0.0, min(line.bbox[0] for line in question_lines) - 2.0)
    x1 = min(page.width, max(line.bbox[2] for line in question_lines) + 2.0)
    if multi_col:
        col = _column_key(question_lines[0], page.width)
        if col == 0:
            x0 = min(x0, 36.0)
            x1 = max(x1, min(page.width * 0.48, page.width - 36.0))
            x1 = min(x1, page.width * 0.5 - 8.0)
        else:
            x0 = min(x0, max(36.0, page.width * 0.52))
            x1 = max(x1, page.width - 36.0)
    else:
        x0 = min(x0, 36.0)
        x1 = max(x1, page.width - 36.0)

    y0 = q_box[3] + 4.0
    if next_question_line is not None:
        y1 = next_question_line.bbox[1] - 4.0
    else:
        y1 = min(page.height - 36.0, y0 + 72.0)

    if y1 <= y0:
        warnings.append("insufficient_answer_space")
        return None, warnings, "low"

    width = x1 - x0
    height = y1 - y0
    if width < MIN_ANSWER_WIDTH or height < MIN_ANSWER_HEIGHT:
        warnings.append("answer_region_too_small")
        return None, warnings, "low"

    if next_question_line is not None and not _same_column(question_lines[0], next_question_line, page.width):
        warnings.append("cross_column_boundary")
        confidence: LayoutConfidenceValue = "low"
    elif next_question_line is None:
        confidence = "medium"
        warnings.append("estimated_answer_region_page_end")
    elif height < 28:
        confidence = "medium"
        warnings.append("tight_answer_region")
    else:
        confidence = "high"

    # Cap very tall answer regions so overlays stay usable.
    if height > 160:
        y1 = y0 + 160
        warnings.append("answer_region_height_capped")
        if confidence == "high":
            confidence = "medium"

    return [float(x0), float(y0), float(x1), float(y1)], warnings, confidence


def detect_layout_questions(pages: list[PageGeometry]) -> tuple[list[LayoutQuestion], list[str], str]:
    """Detect questions and answer regions from page geometry."""
    warnings: list[str] = []
    ordered_lines: list[tuple[PageGeometry, TextLine]] = []
    for page in pages:
        if page.requires_ocr:
            warnings.append(f"page_{page.page_index}_requires_ocr")
            continue
        filtered = filter_header_footer_text_lines(page.lines, page.height)
        for line in _sort_reading_order(filtered, page.width):
            ordered_lines.append((page, line))

    if not ordered_lines and any(p.requires_ocr for p in pages):
        return [], list(dict.fromkeys(warnings + ["requires_ocr"])), "requires_ocr"

    # Prefer Question N labels; fall back to numbered items if none found.
    labeled: list[tuple[int, str, PageGeometry, list[TextLine]]] = []
    i = 0
    while i < len(ordered_lines):
        page, line = ordered_lines[i]
        matched = _match_question_label(line.text)
        if matched and matched[0] == "question":
            _, qid, rest = matched
            q_lines = [line]
            text_parts = [rest] if rest else []
            i += 1
            while i < len(ordered_lines):
                next_page, next_line = ordered_lines[i]
                if next_page.page_index != page.page_index:
                    break
                if _match_question_label(next_line.text) and _match_question_label(next_line.text)[0] == "question":
                    break
                if not _same_column(line, next_line, page.width):
                    # Do not swallow the other column into this question.
                    break
                q_lines.append(next_line)
                text_parts.append(next_line.text)
                i += 1
            labeled.append((qid, "\n".join(p for p in text_parts if p).strip(), page, q_lines))
        else:
            i += 1

    mode = "question"
    if not labeled:
        mode = "numbered"
        i = 0
        while i < len(ordered_lines):
            page, line = ordered_lines[i]
            matched = _match_question_label(line.text)
            if matched and matched[0] == "numbered":
                _, qid, rest = matched
                q_lines = [line]
                text_parts = [rest] if rest else []
                i += 1
                while i < len(ordered_lines):
                    next_page, next_line = ordered_lines[i]
                    if next_page.page_index != page.page_index:
                        break
                    next_match = _match_question_label(next_line.text)
                    if next_match and next_match[0] == "numbered":
                        break
                    if not _same_column(line, next_line, page.width):
                        break
                    q_lines.append(next_line)
                    text_parts.append(next_line.text)
                    i += 1
                body = "\n".join(p for p in text_parts if p).strip()
                if body or qid <= 10:
                    labeled.append((qid, body or f"Question {qid}", page, q_lines))
            else:
                i += 1

    if not labeled:
        # Preserve text fallback for non-OCR documents without question markers.
        if any(p.has_usable_text for p in pages):
            full_text = "\n".join(line.text for _, line in ordered_lines).strip() or "(No extractable text)"
            first_page = next((p for p in pages if p.has_usable_text), pages[0] if pages else None)
            q_bbox = None
            if ordered_lines:
                q_bbox = bbox_list(union_bbox([line.bbox for _, line in ordered_lines[:8]]))
            return (
                [
                    LayoutQuestion(
                        id=0,
                        text=full_text,
                        page_index=first_page.page_index if first_page else None,
                        question_bbox=q_bbox,
                        answer_bbox=None,
                        layout_confidence="low",
                        layout_warnings=["fallback_single_block", "unresolved_answer_region"],
                    )
                ],
                list(dict.fromkeys(warnings + ["fallback_single_block"])),
                "fallback_single_block",
            )
        return [], list(dict.fromkeys(warnings + ["empty_extraction"])), "empty_extraction"

    questions: list[LayoutQuestion] = []
    for index, (qid, text, page, q_lines) in enumerate(labeled):
        next_line = None
        for later_index in range(index + 1, len(labeled)):
            _next_qid, _next_text, next_page, next_lines = labeled[later_index]
            if next_page.page_index != page.page_index:
                break
            if _same_column(q_lines[0], next_lines[0], page.width):
                next_line = next_lines[0]
                break
        answer_bbox, region_warnings, confidence = _propose_answer_bbox(
            question_lines=q_lines,
            next_question_line=next_line,
            page=page,
        )
        q_warnings = list(region_warnings)
        if labeled[index][2].page_index != page.page_index:
            q_warnings.append("cross_page_question")
        question_bbox = bbox_list(union_bbox([line.bbox for line in q_lines]))
        if answer_bbox is None:
            q_warnings.append("unresolved_answer_region")
            confidence = "low"
        questions.append(
            LayoutQuestion(
                id=qid,
                text=text,
                page_index=page.page_index,
                question_bbox=question_bbox,
                answer_bbox=answer_bbox,
                layout_confidence=confidence,
                layout_warnings=q_warnings,
            )
        )

    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        warnings.append("duplicate_question_ids")
    if mode == "numbered":
        warnings.append("numbered_list_detection")
    return questions, list(dict.fromkeys(warnings)), "ok"
