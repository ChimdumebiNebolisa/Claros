"""Hybrid native-PDF, PaddleOCR, and semantic document-understanding pipeline."""
from __future__ import annotations

import hashlib
import math
import re
import time

import fitz

import config
from document_model import (
    BlockSemanticRole,
    DocumentBlock,
    DocumentChoice,
    DocumentPage,
    DocumentResponseRegion,
    DocumentTask,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ResponseRegionType,
    ResponseSafety,
    ReviewStatus,
    SourceKind,
    TaskResponseRole,
    TaskResponseLink,
    page_has_reliable_native_write_evidence,
    source_prompt_text,
    stable_response_region_id,
    stable_task_id,
)
from ocr_adapter import OCRAdapter, NullOCRAdapter, get_ocr_adapter
from semantic_classifier import NullSemanticClassifier, SemanticClassifier

_NATIVE_TEXT_MIN_CHARS = 12
_SAFE_RESPONSE_LABELS = {
    "answer_line",
    "bounded_box",
    "checkbox",
    "form_field",
    "writable_area",
}
_AUTO_APPROVABLE_RESPONSE_LABELS = {
    "answer_line",
    "bounded_box",
    "form_field",
    "writable_area",
}
_RESPONSE_CUE = re.compile(
    r"\b(answer|response|explain|describe|calculate|solve|write|record|select|choose|complete|fill)\b",
    re.IGNORECASE,
)
_CHOICE_TEXT = re.compile(r"^\s*(?:[A-Za-z]|[1-9][0-9]*)\s*[.)]\s+\S")
_ALPHABETIC_CHOICE_TEXT = re.compile(r"^\s*[A-Za-z]\s*[.)]\s+\S")
_NUMBERED_PROMPT = re.compile(r"^\s*\(?[1-9][0-9]*[.)]\s+\S")
_NUMBERED_PROMPT_LABEL = re.compile(r"^\s*\(?([1-9][0-9]*)[.)]\s+\S")
_CHOICE_PROMPT_CUE = re.compile(
    r"\b(?:choose|select|option|choice|correct\s+answer)\b",
    re.IGNORECASE,
)
_TASK_INSTRUCTION_START = re.compile(
    r"^\s*(?:answer|calculate|choose|circle|compare|complete|describe|draw|"
    r"explain|fill|find|identify|label|list|read|record|select|solve|state|use|write)\b",
    re.IGNORECASE,
)
_SHOW_WORK_CUE = re.compile(r"\b(show\s+(?:your\s+)?work|work\s*:|calculations?)\b", re.IGNORECASE)
_EXPLANATION_CUE = re.compile(r"\b(explain|reason|evidence|justify|describe|why)\b", re.IGNORECASE)
_EXPLICIT_RESPONSE_LABEL = re.compile(
    r"^\s*(?:(?:(?:your|final|student)\s+)?(?:answer|response)|"
    r"write\s+(?:your\s+)?answer|show\s+(?:your\s+)?work)\s*:\s*$",
    re.IGNORECASE,
)
_EXPLICIT_RESPONSE_LABEL_SUFFIX = re.compile(
    r"(?:^|[.!?]\s+)(?:(?:(?:your|final|student)\s+)?(?:answer|response)|"
    r"write\s+(?:your\s+)?answer|show\s+(?:your\s+)?work)\s*:\s*$",
    re.IGNORECASE,
)
_NONSTUDENT_WRITE_CUE = re.compile(
    r"(?:\b(?:(?:teacher|instructor|educator)(?:['’]s)?\s+"
    r"(?:guide|notes|copy|edition)|answer\s+(?:key|sheet)|do\s+not\s+write)\b|"
    r"^\s*(?:solutions?|worked\s+(?:solutions?|examples?)|"
    r"facilitator(?:\s+copy)?|trainer\s+(?:guide|notes|copy)|"
    r"answer\s+bank|model\s+answers?)\b)",
    re.IGNORECASE,
)
_MAX_VECTOR_RECTANGLE_CANDIDATES = 256
_MAX_VECTOR_GEOMETRY_ITEMS = 256
_MAX_VECTOR_RULE_CANDIDATES = 256


def _is_task_shaped_prompt(text: str) -> bool:
    return bool(
        _NUMBERED_PROMPT.match(text)
        or re.match(r"^\s*question\s+[1-9][0-9]*\b", text, re.IGNORECASE)
    )


def _is_unnumbered_student_prompt_anchor(text: str) -> bool:
    """Recognize a sentence-case worksheet prompt that is not numbered.

    Word-problem cards often omit a leading ``1.`` marker on the prompt span
    itself. Continuations still have to pass the tight wrap checks below.
    """
    stripped = text.strip()
    if len(stripped) < 12:
        return False
    if _is_explicit_response_label_text(stripped) or _CHOICE_TEXT.match(stripped):
        return False
    return bool(re.match(r"^[A-Z(]", stripped) or _TASK_INSTRUCTION_START.match(stripped))


def _looks_like_new_prompt_line(text: str) -> bool:
    """Reject wrap attachment when the next line begins a new student task."""
    if _is_task_shaped_prompt(text) or _TASK_INSTRUCTION_START.match(text):
        return True
    return bool(
        re.match(
            r"^\s*(?:what|why|how|when|where|which|who)\b",
            text,
            re.IGNORECASE,
        )
    )


def _is_tight_prompt_continuation(
    previous: DocumentBlock,
    candidate: DocumentBlock,
    *,
    first: DocumentBlock,
) -> bool:
    """Return whether candidate is a same-column wrap of the selected prompt."""
    if (
        candidate.bbox is None
        or previous.bbox is None
        or first.bbox is None
        or candidate.source != SourceKind.native_pdf
        or candidate.page_index != first.page_index
        or not candidate.text.strip()
        or previous.text.rstrip().endswith((".", "?", "!", ":"))
        or _looks_like_new_prompt_line(candidate.text)
        or candidate.text.rstrip().endswith(":")
        or _is_explicit_response_label_text(candidate.text)
        or candidate.bbox[1] < previous.bbox[3] - 2
        or candidate.bbox[1] - previous.bbox[3] > 24
        or candidate.bbox[0] < first.bbox[0] - 4
        or candidate.bbox[0] > first.bbox[0] + 48
    ):
        return False
    # Lowercase fragments ("all?") and mid-sentence capitals ("Tuesday") are
    # valid wraps. New interrogatives / imperatives are rejected above.
    return bool(re.match(r"^\s*(?:[a-zA-Z([])", candidate.text))


def _expand_wrapped_prompt_blocks(
    prompt_blocks: list[DocumentBlock],
    all_blocks: list[DocumentBlock],
) -> list[DocumentBlock]:
    """Attach tightly wrapped native continuations to selected prompt evidence.

    Semantic selectors may return only the first visual line of a wrapped
    prompt. Deterministic geometry still owns the remaining source spans so
    association does not leap over unselected prompt text.
    """
    if not prompt_blocks:
        return prompt_blocks
    expanded = list(prompt_blocks)
    selected_ids = {block.id for block in expanded}
    first = expanded[0]
    previous = expanded[-1]
    while True:
        candidates = [
            block
            for block in all_blocks
            if block.id not in selected_ids
            and _is_tight_prompt_continuation(previous, block, first=first)
        ]
        if not candidates:
            break
        nxt = min(
            candidates,
            key=lambda block: (
                block.bbox[1] if block.bbox is not None else float("inf"),
                block.bbox[0] if block.bbox is not None else float("inf"),
                block.reading_order,
                block.id,
            ),
        )
        expanded.append(nxt)
        selected_ids.add(nxt.id)
        previous = nxt
    return expanded


def _is_explicit_response_label_text(text: str) -> bool:
    """Recognize a standalone label or the final label in a prompt sentence."""
    if _EXPLICIT_RESPONSE_LABEL.match(text) or _EXPLICIT_RESPONSE_LABEL_SUFFIX.search(text):
        return True
    stripped = text.strip()
    # Explanation / show-work colon labels are explicit destinations even when
    # they are longer than a bare "Answer:" token.
    return bool(
        stripped.endswith(":")
        and (_SHOW_WORK_CUE.search(stripped) or _EXPLANATION_CUE.search(stripped))
    )


def _prompt_text_has_competing_instruction(text: str) -> bool:
    """Detect merged same-line task text that cannot be split safely.

    Some PDFs place independently positioned spans on one baseline and the
    extractor returns them as one native line. A second imperative after a
    sentence boundary must not inherit the first task's source ID.
    """
    body = re.sub(
        r"^\s*(?:\(?[1-9][0-9]*[.)]\s+|question\s+[1-9][0-9]*\s*[:.)]?\s*)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    for boundary in re.finditer(r"[.!?]\s*", body):
        suffix = body[boundary.end() :].strip()
        if (
            suffix
            and _TASK_INSTRUCTION_START.match(suffix)
            and not _is_explicit_response_label_text(suffix)
        ):
            return True
    return False


def _numbered_prompt_label(text: str) -> int | None:
    match = _NUMBERED_PROMPT_LABEL.match(text)
    return int(match.group(1)) if match else None


def _prompt_looks_like_a_numeric_choice(
    prompt: DocumentBlock,
    all_blocks: list[DocumentBlock],
) -> bool:
    """Reject numeric option labels selected as standalone task prompts."""
    prompt_number = _numbered_prompt_label(prompt.text)
    if prompt_number is None or prompt.bbox is None or not _CHOICE_TEXT.match(prompt.text):
        return False
    for candidate in all_blocks:
        if (
            candidate.id == prompt.id
            or candidate.source != SourceKind.native_pdf
            or candidate.page_index != prompt.page_index
            or candidate.bbox is None
            or candidate.bbox[1] >= prompt.bbox[1] - 2
            or not _CHOICE_PROMPT_CUE.search(candidate.text)
        ):
            continue
        candidate_number = _numbered_prompt_label(candidate.text)
        if candidate_number is None:
            continue
        # Choice lists commonly restart at 1 or repeat the question number;
        # later worksheet questions instead advance numbering at the same
        # left margin. Indented numeric labels are also option-shaped.
        if (
            prompt_number <= candidate_number
            or prompt.bbox[0] >= candidate.bbox[0] + 12
        ):
            return True
        # A later option normally advances its label (``2. Beta``), so the
        # repeated-number check above is not enough. A numbered option-shaped
        # row between the choose/select prompt and this label is physical
        # evidence of a choice run; do not let a model reframe that row as a
        # standalone numbered task.
        if any(
            block.id not in {candidate.id, prompt.id}
            and block.source == SourceKind.native_pdf
            and block.page_index == prompt.page_index
            and block.bbox is not None
            and candidate.bbox[1] + 2 < block.bbox[1] < prompt.bbox[1] - 2
            and abs(block.bbox[0] - prompt.bbox[0]) <= 12
            and _CHOICE_TEXT.match(block.text)
            for block in all_blocks
        ):
            return True
    return False


def _is_deterministic_choice_label(
    block: DocumentBlock,
    all_blocks: list[DocumentBlock],
) -> bool:
    """Recognize source choice labels without mistaking numbered tasks for options."""
    return bool(_ALPHABETIC_CHOICE_TEXT.match(block.text)) or _prompt_looks_like_a_numeric_choice(
        block,
        all_blocks,
    )


def _page_extraction_dimensions(page: fitz.Page) -> tuple[float, float]:
    """Return the unrotated coordinate extent used by PyMuPDF extraction.

    ``Page.rect`` includes crop and ``/UserUnit`` scaling, while a rotated
    page swaps its display width and height. Text, drawings, and widgets are
    exposed in the unrotated extraction frame, so use the de-rotated rect
    dimensions as the canonical bounds.
    """
    rotation = int(page.rotation) % 360
    width = float(page.rect.width)
    height = float(page.rect.height)
    if rotation in {90, 270}:
        return height, width
    return width, height


def _page_extraction_rect(page: fitz.Page) -> fitz.Rect:
    """Unrotated extraction frame matching ``get_text`` / ``get_drawings`` coords."""
    width, height = _page_extraction_dimensions(page)
    media = page.mediabox
    return fitz.Rect(media.x0, media.y0, media.x0 + width, media.y0 + height)


def _page_requires_display_transform(page: fitz.Page) -> bool:
    """Whether extraction coordinates need a transform before browser display."""
    media = page.mediabox
    crop = page.cropbox
    extraction_width, extraction_height = _page_extraction_dimensions(page)
    return page.rotation != 0 or any(
        abs(left - right) > 0.01
        for left, right in zip((media.x0, media.y0, media.x1, media.y1), (crop.x0, crop.y0, crop.x1, crop.y1))
    ) or abs(extraction_width - float(media.width)) > 0.01 or abs(
        extraction_height - float(media.height)
    ) > 0.01


def _clip_bbox_to_page(
    bbox: list[float],
    width: float,
    height: float,
) -> list[float] | None:
    """Clip observed geometry to its active extraction frame, or omit it."""
    if len(bbox) != 4 or not all(math.isfinite(float(value)) for value in bbox):
        return None
    x0, y0, x1, y1 = (float(value) for value in bbox)
    clipped = [max(0.0, x0), max(0.0, y0), min(width, x1), min(height, y1)]
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        return None
    return clipped


def _sanitize_blocks_to_page(
    blocks: list[DocumentBlock],
    *,
    width: float,
    height: float,
) -> tuple[list[DocumentBlock], bool]:
    """Keep only geometry that is valid in the page extraction frame.

    PDF drawing and OCR APIs can return content clipped by the active page
    frame. The text and stable ID remain useful evidence, but a clipped
    response source must never become an auto-approved physical destination.
    """
    sanitized: list[DocumentBlock] = []
    changed_any = False
    for block in blocks:
        clipped_bbox = _clip_bbox_to_page(block.bbox, width, height) if block.bbox else None
        geometry_changed = block.bbox is not None and clipped_bbox != block.bbox
        polygon_outside = block.polygon is not None and any(
            x < 0 or y < 0 or x > width or y > height for x, y in block.polygon
        )
        updates = {}
        if geometry_changed:
            updates["bbox"] = clipped_bbox
        if polygon_outside or clipped_bbox is None and block.bbox is not None:
            updates["polygon"] = None
        if geometry_changed and block.block_label in _SAFE_RESPONSE_LABELS:
            updates["block_label"] = "clipped_response_candidate"
            updates["semantic_role"] = BlockSemanticRole.unknown
        if updates:
            block = block.model_copy(update=updates)
            changed_any = True
        sanitized.append(block)
    return sanitized, changed_any


def _stable_physical_block_id(
    page_index: int,
    kind: str,
    bbox: list[float],
    *,
    discriminator: str = "",
) -> str:
    """Derive physical evidence IDs from source geometry, never OCR order."""
    fingerprint = ":".join(
        [str(page_index), kind, *(f"{float(value):.3f}" for value in bbox), discriminator]
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"page-{page_index}-{kind}-{digest}"


def _bbox_interiors_overlap(first: list[float], second: list[float]) -> bool:
    return (
        max(first[0], second[0]) < min(first[2], second[2])
        and max(first[1], second[1]) < min(first[3], second[3])
    )


def _fill_is_paper_like(fill: object) -> bool:
    """Return whether a vector fill is blank worksheet paper rather than content.

    Pale card backgrounds and white field interiors are common on selectable-text
    worksheets. They must not erase visible prompt text or reject empty writable
    boxes. Dark fills still count as covering content.
    """
    if fill is None:
        return True
    if not isinstance(fill, (list, tuple)) or len(fill) < 3:
        return False
    try:
        channels = [float(value) for value in fill[:3]]
    except (TypeError, ValueError):
        return False
    return min(channels) >= 0.92


def _drawing_is_closed_frame(drawing: dict) -> bool:
    """Recognize closed stroked frames, including rounded rectangles.

    ReportLab and similar producers encode rounded boxes as line/curve cycles
    rather than rectangle operators. The drawing rect is still physical evidence.
    """
    items = [item for item in drawing.get("items") or [] if item]
    if not items:
        return False
    operators = {item[0] for item in items}
    if operators <= {"re"}:
        return True
    if "re" in operators:
        return True
    # Closed rounded/rectangular frames use only line and curve segments.
    return operators <= {"l", "c", "v", "y", "qu"} and len(items) >= 4


def _bbox_has_page_graphics(
    bbox: list[float],
    *,
    drawings: list[dict],
    image_bboxes: list[list[float]],
) -> bool:
    """Return whether covering graphics hide the evidence region.

    Paper-like card fills and rounded frame strokes are worksheet chrome, not
    proof that selectable text is hidden. Raster images and dark fills still
    fail closed.
    """
    if any(_bbox_interiors_overlap(bbox, image_bbox) for image_bbox in image_bboxes):
        return True
    inner = [bbox[0] + 2, bbox[1] + 2, bbox[2] - 2, bbox[3] - 2]
    if inner[2] <= inner[0] or inner[3] <= inner[1]:
        return True
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None:
            continue
        drawing_bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        fill = drawing.get("fill")
        if (
            fill is not None
            and not _fill_is_paper_like(fill)
            and _bbox_interiors_overlap(bbox, drawing_bbox)
        ):
            return True
        for item in drawing.get("items", []):
            if not item:
                continue
            if item[0] == "l":
                p0, p1 = item[1], item[2]
                x0, x1 = sorted((float(p0.x), float(p1.x)))
                y0, y1 = sorted((float(p0.y), float(p1.y)))
                if not (x1 < inner[0] or x0 > inner[2] or y1 < inner[1] or y0 > inner[3]):
                    return True
            elif item[0] == "re":
                shape = item[1]
                if _bbox_interiors_overlap(
                    inner,
                    [float(shape.x0), float(shape.y0), float(shape.x1), float(shape.y1)],
                ) and (
                    any(inner[0] < x < inner[2] for x in (shape.x0, shape.x1))
                    or any(inner[1] < y < inner[3] for y in (shape.y0, shape.y1))
                ):
                    return True
            elif (
                not _fill_is_paper_like(fill)
                and not _drawing_is_closed_frame(drawing)
                and _bbox_interiors_overlap(inner, drawing_bbox)
            ):
                return True
    return False


def _vector_geometry_within_budget(drawings: list[dict]) -> bool:
    """Bound vector-derived write evidence before any pairwise geometry work."""
    count = 0
    for drawing in drawings:
        for item in drawing.get("items", []):
            if item and item[0] in {"l", "re"}:
                count += 1
                if count > _MAX_VECTOR_GEOMETRY_ITEMS:
                    return False
    return True


def _render_visibility_pixmap(page: fitz.Page, *, annots: bool) -> fitz.Pixmap | None:
    """Render the unrotated extraction frame for visibility proofs.

    Extraction geometry is unrotated. ``page.rect`` / default pixmap rendering
    follow the display rotation, so a 90-degree page would sample the wrong
    pixels unless rotation is cleared for this proof render only.
    """
    rotation = int(page.rotation) % 360
    try:
        if rotation:
            page.set_rotation(0)
        return page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False, annots=annots)
    except Exception:
        return None
    finally:
        if rotation:
            page.set_rotation(rotation)


def _page_visibility_pixmap(page: fitz.Page) -> fitz.Pixmap | None:
    """Render a bounded source view used only to prove native glyph visibility.

    PDF text extraction retains hidden layers and text painted over by later
    graphics. Those glyphs cannot authorize a write target. A modest render is
    enough to distinguish visible ink from an invisible source-text layer; a
    renderer failure fails closed for native write evidence.
    """
    # Keep annotation appearance separate from source-page pixels. Widget
    # extraction compares this base render to an explicit annots=True
    # render, while native/vector evidence must not inherit a widget AP.
    return _render_visibility_pixmap(page, annots=False)


def _page_annotation_visibility_pixmap(page: fitz.Page) -> fitz.Pixmap | None:
    """Render visible annotations to prove that a widget paints on the page.

    A widget rectangle and visible annotation flags alone do not prove that a
    student can see a response destination.  Empty AcroForms can carry those
    coordinates while their appearance stream paints nothing.  Rendering the
    page with annotations lets the parser require an actual, local visual
    change without trusting the widget metadata as a proxy for visibility.
    """
    return _render_visibility_pixmap(page, annots=True)


def _widget_has_rendered_appearance(
    page: fitz.Page,
    source_pixmap: fitz.Pixmap | None,
    annotation_pixmap: fitz.Pixmap | None,
    bbox: list[float],
) -> bool:
    """Require a widget's local annotation rendering to change source pixels."""
    if (
        source_pixmap is None
        or annotation_pixmap is None
        or source_pixmap.width != annotation_pixmap.width
        or source_pixmap.height != annotation_pixmap.height
        or source_pixmap.n < 3
        or annotation_pixmap.n < 3
    ):
        return False
    page_rect = _page_extraction_rect(page)
    if page_rect.width <= 0 or page_rect.height <= 0:
        return False
    scale_x = source_pixmap.width / float(page_rect.width)
    scale_y = source_pixmap.height / float(page_rect.height)
    # Include the physical border: PDF appearance streams commonly inset it by
    # half a point from the widget rectangle.
    x0 = max(0, int(math.floor((bbox[0] - 1 - page_rect.x0) * scale_x)))
    y0 = max(0, int(math.floor((bbox[1] - 1 - page_rect.y0) * scale_y)))
    x1 = min(
        source_pixmap.width,
        int(math.ceil((bbox[2] + 1 - page_rect.x0) * scale_x)),
    )
    y1 = min(
        source_pixmap.height,
        int(math.ceil((bbox[3] + 1 - page_rect.y0) * scale_y)),
    )
    if x1 <= x0 or y1 <= y0:
        return False
    sample_count = (x1 - x0) * (y1 - y0)
    stride = max(1, int(math.ceil(math.sqrt(sample_count / 24_000))))
    changed_samples = 0
    for y in range(y0, y1, stride):
        source_row = y * source_pixmap.stride
        annotation_row = y * annotation_pixmap.stride
        for x in range(x0, x1, stride):
            source_offset = source_row + x * source_pixmap.n
            annotation_offset = annotation_row + x * annotation_pixmap.n
            if (
                source_offset + 2 >= len(source_pixmap.samples)
                or annotation_offset + 2 >= len(annotation_pixmap.samples)
            ):
                return False
            difference = math.sqrt(
                sum(
                    (
                        source_pixmap.samples[source_offset + channel]
                        - annotation_pixmap.samples[annotation_offset + channel]
                    )
                    ** 2
                    for channel in range(3)
                )
            )
            if difference >= 24:
                changed_samples += 1
                if changed_samples >= 4:
                    return True
    return False


def _bbox_has_rendered_base_content(
    page: fitz.Page,
    visibility_pixmap: fitz.Pixmap | None,
    bbox: list[float],
) -> bool:
    """Reject a widget when non-annotation content occupies its interior."""
    if visibility_pixmap is None:
        return True
    page_rect = _page_extraction_rect(page)
    if page_rect.width <= 0 or page_rect.height <= 0:
        return True
    inner = [bbox[0] + 2, bbox[1] + 2, bbox[2] - 2, bbox[3] - 2]
    if inner[2] <= inner[0] or inner[3] <= inner[1]:
        return True
    scale_x = visibility_pixmap.width / float(page_rect.width)
    scale_y = visibility_pixmap.height / float(page_rect.height)
    x0 = max(0, int(math.floor((inner[0] - page_rect.x0) * scale_x)))
    y0 = max(0, int(math.floor((inner[1] - page_rect.y0) * scale_y)))
    x1 = min(visibility_pixmap.width, int(math.ceil((inner[2] - page_rect.x0) * scale_x)))
    y1 = min(visibility_pixmap.height, int(math.ceil((inner[3] - page_rect.y0) * scale_y)))
    if x1 <= x0 or y1 <= y0:
        return True
    sample_count = (x1 - x0) * (y1 - y0)
    stride = max(1, int(math.ceil(math.sqrt(sample_count / 24_000))))
    for y in range(y0, y1, stride):
        row_offset = y * visibility_pixmap.stride
        for x in range(x0, x1, stride):
            offset = row_offset + x * visibility_pixmap.n
            if offset + 2 >= len(visibility_pixmap.samples):
                return True
            # Source-page ink or graphics inside the field would be covered
            # by an export.  A visible worksheet field must start blank.
            if any(visibility_pixmap.samples[offset + channel] < 220 for channel in range(3)):
                return True
    return False


def _vector_segment_has_rendered_contrast(
    page: fitz.Page,
    visibility_pixmap: fitz.Pixmap | None,
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    """Prove a horizontal or vertical vector stroke is visibly rendered.

    Vector metadata alone is not authority: a white, transparent, hidden, or
    covered rule has the same PDF geometry as a visible answer line. Compare
    pixels on the stroke to local perpendicular background samples instead.
    """
    if visibility_pixmap is None:
        return False
    page_rect = _page_extraction_rect(page)
    if page_rect.width <= 0 or page_rect.height <= 0:
        return False
    x0, y0 = start
    x1, y1 = end
    horizontal = abs(y1 - y0) <= 2
    vertical = abs(x1 - x0) <= 2
    if not horizontal and not vertical:
        return False
    scale_x = visibility_pixmap.width / float(page_rect.width)
    scale_y = visibility_pixmap.height / float(page_rect.height)

    def pixel_rgb(x: int, y: int) -> tuple[int, int, int] | None:
        if x < 0 or y < 0 or x >= visibility_pixmap.width or y >= visibility_pixmap.height:
            return None
        offset = y * visibility_pixmap.stride + x * visibility_pixmap.n
        samples = visibility_pixmap.samples
        if offset + 2 >= len(samples):
            return None
        return samples[offset], samples[offset + 1], samples[offset + 2]

    length = abs(x1 - x0) if horizontal else abs(y1 - y0)
    sample_count = max(5, min(25, int(length / 14)))
    visible_samples = 0
    total_samples = 0
    for index in range(sample_count):
        fraction = (index + 1) / (sample_count + 1)
        point_x = x0 + (x1 - x0) * fraction
        point_y = y0 + (y1 - y0) * fraction
        pixel_x = int(round((point_x - page_rect.x0) * scale_x))
        pixel_y = int(round((point_y - page_rect.y0) * scale_y))
        if horizontal:
            stroke_pixels = [pixel_rgb(pixel_x, pixel_y + delta) for delta in (-1, 0, 1)]
            background_pixels = [pixel_rgb(pixel_x, pixel_y + delta) for delta in (-5, 5)]
        else:
            stroke_pixels = [pixel_rgb(pixel_x + delta, pixel_y) for delta in (-1, 0, 1)]
            background_pixels = [pixel_rgb(pixel_x + delta, pixel_y) for delta in (-5, 5)]
        stroke = [value for value in stroke_pixels if value is not None]
        background = [value for value in background_pixels if value is not None]
        if not stroke or not background:
            continue
        total_samples += 1
        contrast = max(
            math.sqrt(sum((ink[channel] - paper[channel]) ** 2 for channel in range(3)))
            for ink in stroke
            for paper in background
        )
        if contrast >= 36:
            visible_samples += 1
    return total_samples >= 3 and visible_samples * 2 >= total_samples


def _rectangle_outline_has_rendered_contrast(
    page: fitz.Page,
    visibility_pixmap: fitz.Pixmap | None,
    bbox: list[float],
) -> bool:
    """Require all four outline sides of a bounded response box to be visible."""
    x0, y0, x1, y1 = bbox
    return (
        x1 > x0
        and y1 > y0
        and _vector_segment_has_rendered_contrast(page, visibility_pixmap, (x0, y0), (x1, y0))
        and _vector_segment_has_rendered_contrast(page, visibility_pixmap, (x0, y1), (x1, y1))
        and _vector_segment_has_rendered_contrast(page, visibility_pixmap, (x0, y0), (x0, y1))
        and _vector_segment_has_rendered_contrast(page, visibility_pixmap, (x1, y0), (x1, y1))
    )


def _span_rgb(span: dict) -> tuple[int, int, int]:
    """Normalize PyMuPDF's packed RGB span color without trusting defaults."""
    try:
        color = int(span.get("color", 0))
    except (TypeError, ValueError):
        color = 0
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def _span_has_rendered_visibility(
    page: fitz.Page,
    span: dict,
    visibility_pixmap: fitz.Pixmap | None,
    *,
    bbox: list[float] | tuple[float, float, float, float] | None = None,
) -> bool:
    """Require opaque, contrasting rendered ink for native write evidence.

    This deliberately accepts a smaller supported subset of PDFs. It rejects
    transparent/white text, text hidden under a later fill or image, and text
    whose rendered bounding box has no visible foreground/background contrast.
    The parser can still route such pages to the typed side panel.
    """
    if int(span.get("alpha", 255) if span.get("alpha") is not None else 255) != 255:
        return False
    if visibility_pixmap is None:
        return False
    expected = _span_rgb(span)
    luminance = (
        0.2126 * expected[0] + 0.7152 * expected[1] + 0.0722 * expected[2]
    ) / 255
    # Very light ink cannot supply a deterministic contrast proof against the
    # normal worksheet background. Preserve it as unsupported rather than
    # infer visibility from source metadata alone.
    if luminance > 0.75:
        return False
    raw_bbox = bbox if bbox is not None else span.get("bbox")
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return False
    page_rect = _page_extraction_rect(page)
    if page_rect.width <= 0 or page_rect.height <= 0:
        return False
    scale_x = visibility_pixmap.width / float(page_rect.width)
    scale_y = visibility_pixmap.height / float(page_rect.height)
    # Raw character boxes can stop exactly at a thin underscore's baseline;
    # include one physical point of surrounding rendered pixels so visible
    # thin glyphs are not mistaken for hidden layers.
    padding = 1.0 if bbox is not None else 0.0
    x0 = max(0, int(math.floor((float(raw_bbox[0]) - padding - page_rect.x0) * scale_x)))
    y0 = max(0, int(math.floor((float(raw_bbox[1]) - padding - page_rect.y0) * scale_y)))
    x1 = min(visibility_pixmap.width, int(math.ceil((float(raw_bbox[2]) + padding - page_rect.x0) * scale_x)))
    y1 = min(visibility_pixmap.height, int(math.ceil((float(raw_bbox[3]) + padding - page_rect.y0) * scale_y)))
    if x1 <= x0 or y1 <= y0:
        return False
    sample_count = (x1 - x0) * (y1 - y0)
    # Keep adversarial giant text boxes bounded while preserving enough points
    # to find normal glyph stems and their local background.
    stride = max(1, int(math.ceil(math.sqrt(sample_count / 24_000))))
    samples = visibility_pixmap.samples
    components = visibility_pixmap.n
    # Thin rendered glyphs (notably underscore runs) are antialiased into
    # mid-gray pixels even when their source ink is black. The independent
    # graphics-overlap gate below prevents an unrelated vector artifact from
    # satisfying this broader ink tolerance.
    expected_distance = 240
    has_foreground = False
    has_background = False
    for y in range(y0, y1, stride):
        row_offset = y * visibility_pixmap.stride
        for x in range(x0, x1, stride):
            offset = row_offset + x * components
            if offset + 2 >= len(samples):
                return False
            distance = (
                (samples[offset] - expected[0]) ** 2
                + (samples[offset + 1] - expected[1]) ** 2
                + (samples[offset + 2] - expected[2]) ** 2
            ) ** 0.5
            if distance <= expected_distance:
                has_foreground = True
            elif distance >= expected_distance + 32:
                has_background = True
            if has_foreground and has_background:
                return True
    return False


def _underscore_run_bboxes(
    page: fitz.Page,
    visibility_pixmap: fitz.Pixmap | None,
) -> list[tuple[list[float], str, str]]:
    """Return actual glyph bounds for explicit underscore blanks.

    Character-count interpolation is unsafe for proportional fonts: it can
    place a writable box over prompt text. Raw glyph boxes are source evidence.
    """
    runs: list[tuple[list[float], str, str]] = []
    raw = page.get_text("rawdict", sort=True)
    for raw_block in raw.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        for line in raw_block.get("lines", []):
            # A blank can span font/style runs. Keeping the full physical line
            # also lets us reject identifiers such as ``foo___bar`` rather
            # than treating their punctuation as a response destination.
            chars = [
                char
                for span in line.get("spans", [])
                for char in list(span.get("chars") or [])
                if _span_has_rendered_visibility(
                    page,
                    span,
                    visibility_pixmap,
                    bbox=char.get("bbox"),
                )
            ]
            text = "".join(str(char.get("c") or "") for char in chars)
            for match in re.finditer(r"_{3,}", text):
                preceding = text[match.start() - 1 : match.start()]
                following = text[match.end() : match.end() + 1]
                if (preceding and (preceding.isalnum() or preceding == "_")) or (
                    following and (following.isalnum() or following == "_")
                ):
                    continue
                glyphs = chars[match.start() : match.end()]
                boxes = [glyph.get("bbox") for glyph in glyphs]
                if not boxes or any(not bbox or len(bbox) != 4 for bbox in boxes):
                    continue
                bbox = [
                    min(float(item[0]) for item in boxes),
                    min(float(item[1]) for item in boxes),
                    max(float(item[2]) for item in boxes),
                    max(float(item[3]) for item in boxes),
                ]
                expanded = [bbox[0] - 2, bbox[1] - 3, bbox[2] + 2, bbox[3] + 15]
                overlaps_other_text = False
                for index, char in enumerate(chars):
                    char_text = str(char.get("c") or "")
                    other_bbox = char.get("bbox")
                    if (
                        match.start() <= index < match.end()
                        or not char_text.strip()
                        or char_text == "_"
                        or not other_bbox
                        or len(other_bbox) != 4
                    ):
                        continue
                    other_glyph_bbox = [float(value) for value in other_bbox]
                    if not _bbox_interiors_overlap(expanded, other_glyph_bbox):
                        continue
                    terminal_punctuation = (
                        char_text in ".,;:!?()[]{}"
                        and index in {match.start() - 1, match.end()}
                    )
                    if terminal_punctuation and not _bbox_interiors_overlap(bbox, other_glyph_bbox):
                        continue
                    overlaps_other_text = True
                    break
                if overlaps_other_text:
                    continue
                runs.append((bbox, text[match.start() : match.end()], text))
    return runs


def _vector_rectangle_bboxes(
    drawings: list[dict],
) -> tuple[list[list[float]], list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Return closed vector rectangles plus horizontal and vertical segments.

    PDFs encode boxes either as rectangle operators or as four independent
    line operators. Treat both encodings as the same physical evidence while
    preserving table-grid detection for the caller.
    """
    if not _vector_geometry_within_budget(drawings):
        # Never treat a partial vector subset as physical write evidence.
        return [], [], []

    direct_rectangles: dict[tuple[float, float, float, float], list[float]] = {}
    reconstructed_rectangles: dict[tuple[float, float, float, float], list[float]] = {}
    horizontals: list[tuple[float, float, float]] = []
    verticals: list[tuple[float, float, float]] = []
    tolerance = 2.0

    def rectangle_key(raw_bbox: list[float]) -> tuple[float, float, float, float]:
        return tuple(round(value, 3) for value in raw_bbox)

    def add_reconstructed_rectangle(raw_bbox: list[float]) -> bool:
        key = rectangle_key(raw_bbox)
        if key in direct_rectangles or key in reconstructed_rectangles:
            return True
        if len(reconstructed_rectangles) >= _MAX_VECTOR_RECTANGLE_CANDIDATES:
            return False
        reconstructed_rectangles[key] = raw_bbox
        return True

    direct_rectangle_overflow = False

    def add_direct_rectangle(raw_bbox: list[float]) -> None:
        nonlocal direct_rectangle_overflow
        key = rectangle_key(raw_bbox)
        if key in direct_rectangles:
            return
        if len(direct_rectangles) >= _MAX_VECTOR_RECTANGLE_CANDIDATES:
            direct_rectangle_overflow = True
            return
        direct_rectangles[key] = raw_bbox

    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item:
                continue
            if item[0] == "re":
                rect = item[1]
                add_direct_rectangle([float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)])
            elif item[0] == "l":
                p0, p1 = item[1], item[2]
                if abs(p0.y - p1.y) <= tolerance and abs(p1.x - p0.x) >= 8:
                    horizontals.append((min(float(p0.x), float(p1.x)), max(float(p0.x), float(p1.x)), float((p0.y + p1.y) / 2)))
                elif abs(p0.x - p1.x) <= tolerance and abs(p1.y - p0.y) >= 8:
                    verticals.append((float((p0.x + p1.x) / 2), min(float(p0.y), float(p1.y)), max(float(p0.y), float(p1.y))))

    if direct_rectangle_overflow:
        # A page with more than the bounded candidate budget is visually
        # ambiguous at this extraction layer. Do not expose a partial subset
        # as writable evidence.
        return [], horizontals, verticals

    # Match horizontal sides with the same endpoints, then verify their two
    # vertical edges. This remains bounded for tables: it avoids the prior
    # vertical-pair × horizontal-pair expansion on dense grids, while still
    # recognizing a line-encoded standalone response box beside a grid.
    horizontal_groups: dict[tuple[float, float], list[tuple[float, float, float]]] = {}
    for horizontal in horizontals:
        key = (round(horizontal[0], 1), round(horizontal[1], 1))
        horizontal_groups.setdefault(key, []).append(horizontal)
    for lines in horizontal_groups.values():
        if len(lines) > 32:
            # Extremely dense repeated spans are a grid; do not construct
            # every nested rectangle from it.
            continue
        sorted_lines = sorted(lines, key=lambda item: item[2])
        for top_index, top in enumerate(sorted_lines):
            for bottom in sorted_lines[top_index + 1 :]:
                x0, x1 = top[0], top[1]
                y0, y1 = top[2], bottom[2]
                if y1 - y0 < 8:
                    continue
                has_left = any(
                    abs(vertical[0] - x0) <= tolerance
                    and vertical[1] <= y0 + tolerance
                    and vertical[2] >= y1 - tolerance
                    for vertical in verticals
                )
                has_right = any(
                    abs(vertical[0] - x1) <= tolerance
                    and vertical[1] <= y0 + tolerance
                    and vertical[2] >= y1 - tolerance
                    for vertical in verticals
                )
                if has_left and has_right:
                    if not add_reconstructed_rectangle([x0, y0, x1, y1]):
                        # Do not materialize a partial line-grid subset; keep
                        # any direct rectangle operators, which have their own
                        # bounded provenance, and route line geometry aside.
                        return (
                            [direct_rectangles[key] for key in sorted(direct_rectangles)],
                            horizontals,
                            verticals,
                        )

    return (
        [
            {**direct_rectangles, **reconstructed_rectangles}[key]
            for key in sorted({**direct_rectangles, **reconstructed_rectangles})
        ],
        horizontals,
        verticals,
    )


def _closed_frame_bboxes(drawings: list[dict]) -> list[list[float]]:
    """Collect stroked closed frames, including rounded boxes, by drawing bounds.

    Direct rectangle operators and four-line reconstructions already cover sharp
    boxes. This path adds closed line/curve frames whose physical destination is
    the drawing rectangle itself.
    """
    frames: dict[tuple[float, float, float, float], list[float]] = {}
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None or not _drawing_is_closed_frame(drawing):
            continue
        # Require a visible stroke. Fill-only panels are not writable frames.
        stroke = drawing.get("color")
        width = float(drawing.get("width") or 0)
        if stroke is None or width <= 0:
            continue
        if drawing.get("fill") is not None and not _fill_is_paper_like(drawing.get("fill")):
            continue
        raw_bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        if raw_bbox[2] - raw_bbox[0] < 8 or raw_bbox[3] - raw_bbox[1] < 8:
            continue
        key = tuple(round(value, 3) for value in raw_bbox)
        frames.setdefault(key, raw_bbox)
    return [frames[key] for key in sorted(frames)]


def _native_blocks(
    page: fitz.Page,
    page_index: int,
    *,
    visibility_pixmap: fitz.Pixmap | None = None,
    drawings: list[dict] | None = None,
    image_bboxes: list[list[float]] | None = None,
) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    order = 0
    if visibility_pixmap is None:
        visibility_pixmap = _page_visibility_pixmap(page)
    if drawings is None:
        drawings = page.get_drawings()
    if image_bboxes is None:
        image_bboxes = [
            [float(value) for value in raw_block["bbox"]]
            for raw_block in page.get_text("dict", sort=True).get("blocks", [])
            if raw_block.get("type") == 1
            and isinstance(raw_block.get("bbox"), (list, tuple))
            and len(raw_block["bbox"]) == 4
        ]
    raw = page.get_text("dict", sort=True)
    for raw_block in raw.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        for line in raw_block.get("lines", []):
            visible_spans = [
                span
                for span in line.get("spans", [])
                if _span_has_rendered_visibility(page, span, visibility_pixmap)
                and not _bbox_has_page_graphics(
                    [float(value) for value in span["bbox"]],
                    drawings=drawings,
                    image_bboxes=image_bboxes,
                )
            ]
            text = " ".join(
                str(span.get("text") or "").strip()
                for span in visible_spans
                if str(span.get("text") or "").strip()
            ).strip()
            if not text:
                continue
            span_bboxes = [span.get("bbox") for span in visible_spans if span.get("bbox")]
            raw_bbox = (
                [
                    min(float(bbox[0]) for bbox in span_bboxes),
                    min(float(bbox[1]) for bbox in span_bboxes),
                    max(float(bbox[2]) for bbox in span_bboxes),
                    max(float(bbox[3]) for bbox in span_bboxes),
                ]
                if span_bboxes
                else line.get("bbox") or raw_block.get("bbox")
            )
            if not raw_bbox or len(raw_bbox) != 4:
                continue
            bbox = [float(value) for value in raw_bbox]
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue
            blocks.append(
                DocumentBlock(
                    id=f"page-{page_index}-native-{order}",
                    page_index=page_index,
                    reading_order=order,
                    text=text,
                    block_label="native_text",
                    bbox=bbox,
                    polygon=None,
                    confidence=1.0,
                    source=SourceKind.native_pdf,
                )
            )
            order += 1
    return blocks


def has_reliable_native_page_text(blocks: list[DocumentBlock]) -> bool:
    """Require enough source-native text before it can authorize placement."""
    return sum(len(block.text.strip()) for block in blocks) >= _NATIVE_TEXT_MIN_CHARS


def page_has_nonstudent_write_cue(blocks: list[DocumentBlock]) -> bool:
    """Detect source text that deterministically forbids worksheet writes."""
    return any(_NONSTUDENT_WRITE_CUE.search(block.text) for block in blocks if block.text.strip())


def page_has_nonstudent_write_cue_in_source(page: fitz.Page) -> bool:
    """Fail closed on a nonstudent cue even when its text is decorative.

    This is a negative authorization signal: accepting a hidden or
    graphic-overlapped cue can only route a page to the side panel, never grant
    a write. It therefore intentionally reads all source-native text instead
    of the stricter visible-glyph subset used to authorize student prompts.
    """
    raw = page.get_text("dict", sort=True)
    source_parts: list[str] = []
    for raw_block in raw.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        line_texts: list[str] = []
        for line in raw_block.get("lines", []):
            spans = [str(span.get("text") or "") for span in line.get("spans", [])]
            source_parts.extend(part for part in spans if part.strip())
            line_text = "".join(spans)
            # Adjacent spans can use distinct fonts and omit the original
            # whitespace in their individual text payloads. This is only a
            # negative authorization gate, so preserve both interpretations.
            if _NONSTUDENT_WRITE_CUE.search(line_text) or _NONSTUDENT_WRITE_CUE.search(
                " ".join(part.strip() for part in spans if part.strip())
            ):
                return True
            line_texts.append(line_text)
        if _NONSTUDENT_WRITE_CUE.search("\n".join(line_texts)):
            return True
    # Some PDF producers split a single visible title across raw lines or
    # blocks when font resources change. For this fail-closed gate, a
    # page-wide normalized reading is safer than treating the fragments as
    # unrelated text.
    return bool(_NONSTUDENT_WRITE_CUE.search(" ".join(part.strip() for part in source_parts)))


def _physical_response_blocks(
    page: fitz.Page,
    page_index: int,
    start_order: int,
    native_blocks: list[DocumentBlock],
    *,
    visibility_pixmap: fitz.Pixmap | None = None,
) -> list[DocumentBlock]:
    """Extract deterministic writable candidates without guessing whitespace."""
    blocks: list[DocumentBlock] = []
    order = start_order
    page_width, page_height = _page_extraction_dimensions(page)

    def append_block(
        *,
        kind: str,
        bbox: list[float],
        block_label: str,
        confidence: float,
        response_area: bool,
        discriminator: str = "",
    ) -> None:
        nonlocal order
        clipped = _clip_bbox_to_page(bbox, page_width, page_height)
        if clipped is None:
            return
        geometry_clipped = clipped != bbox
        safe_label = block_label in _SAFE_RESPONSE_LABELS and not geometry_clipped and response_area
        blocks.append(
            DocumentBlock(
                id=_stable_physical_block_id(
                    page_index,
                    kind,
                    clipped,
                    discriminator=discriminator,
                ),
                page_index=page_index,
                reading_order=order,
                text="",
                block_label=("clipped_response_candidate" if geometry_clipped else block_label),
                bbox=clipped,
                confidence=confidence if safe_label else min(confidence, 0.55),
                source=SourceKind.pdf_geometry,
                semantic_role=(
                    BlockSemanticRole.response_area if safe_label else BlockSemanticRole.unknown
                ),
            )
        )
        order += 1

    def nearby_text(bbox: list[float], *, vertical_limit: float = 72.0) -> list[DocumentBlock]:
        nearby: list[DocumentBlock] = []
        for native in native_blocks:
            if native.bbox is None:
                continue
            same_row = (
                native.bbox[0] <= bbox[2] + 24
                and native.bbox[2] >= bbox[0] - 24
                and native.bbox[1] <= bbox[3]
                and native.bbox[3] >= bbox[1] - 18
            )
            above = (
                native.bbox[3] <= bbox[1] + 8
                and bbox[1] - native.bbox[3] <= vertical_limit
                and native.bbox[2] >= bbox[0] - 24
                and native.bbox[0] <= bbox[2] + 24
            )
            if same_row or above:
                nearby.append(native)
        return nearby

    def has_explicit_response_evidence(bbox: list[float]) -> bool:
        nearby = nearby_text(bbox)
        explicit_response_label = any(
            _is_explicit_response_label_text(block.text) for block in nearby
        )
        # A generic metadata field such as "Name:" cannot inherit write
        # authority from an unrelated nearby task. Only a narrowly named,
        # visible response label can make geometry eligible; task ownership is
        # proved later by _response_matches_prompt, including its competing
        # prompt checks, so right-aligned labels remain supported.
        return explicit_response_label

    def has_interior_text(bbox: list[float]) -> bool:
        return any(
            native.bbox is not None
            and _bbox_interiors_overlap(bbox, native.bbox)
            and native.text.strip()
            for native in native_blocks
        )

    page_drawings = page.get_drawings()
    page_image_bboxes = [
        [float(value) for value in raw_block["bbox"]]
        for raw_block in page.get_text("dict", sort=True).get("blocks", [])
        if raw_block.get("type") == 1
        and isinstance(raw_block.get("bbox"), (list, tuple))
        and len(raw_block["bbox"]) == 4
    ]

    def widget_is_viewable(widget) -> bool:
        """Require an AcroForm annotation to be visible in the page view."""
        annotation_flags = 0
        try:
            _kind, raw_flags = page.parent.xref_get_key(widget.xref, "F")
            annotation_flags = int(raw_flags)
        except (AttributeError, TypeError, ValueError):
            # Unknown annotation state cannot become a physical write target.
            return False
        if annotation_flags & (1 | 2 | 32):  # invisible, hidden, or no-view
            return False
        # PyMuPDF exposes hidden/no-view states independently of the raw flag
        # value on some producers. Visible controls are display state zero.
        return int(getattr(widget, "field_display", 0) or 0) == 0

    widget_bboxes: list[list[float]] = []
    widgets = list(page.widgets() or [])
    annotation_visibility_pixmap = (
        _page_annotation_visibility_pixmap(page) if widgets else None
    )
    if widgets:
        for widget in widgets:
            rect = widget.rect
            bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
            widget_bboxes.append(bbox)
            field_type = int(getattr(widget, "field_type", -1) or -1)
            field_flags = int(getattr(widget, "field_flags", 0) or 0)
            field_name = str(getattr(widget, "field_name", "") or "")
            if (
                not widget_is_viewable(widget)
                or field_flags & int(getattr(fitz, "PDF_FIELD_IS_READ_ONLY", 1))
                or not _widget_has_rendered_appearance(
                    page,
                    visibility_pixmap,
                    annotation_visibility_pixmap,
                    bbox,
                )
            ):
                continue
            if has_interior_text(bbox) or _bbox_has_rendered_base_content(
                page,
                visibility_pixmap,
                bbox,
            ):
                continue
            if field_type in {
                int(getattr(fitz, "PDF_WIDGET_TYPE_CHECKBOX", 2)),
                int(getattr(fitz, "PDF_WIDGET_TYPE_RADIOBUTTON", 5)),
            }:
                if (
                    8 <= rect.width <= 48
                    and 8 <= rect.height <= 48
                    and max(rect.width, rect.height) / min(rect.width, rect.height) <= 1.5
                    and str(getattr(widget, "field_value", "") or "").strip().casefold()
                    in {"", "off"}
                ):
                    append_block(
                        kind="checkbox",
                        bbox=bbox,
                        block_label="checkbox",
                        confidence=1.0,
                        response_area=True,
                        discriminator=field_name,
                    )
                continue
            if field_type != int(getattr(fitz, "PDF_WIDGET_TYPE_TEXT", 7)):
                continue
            if rect.width < 24 or rect.height < 18 or str(getattr(widget, "field_value", "") or "").strip():
                continue
            if (
                rect.width <= 32
                and rect.height <= 32
                and max(rect.width, rect.height) / min(rect.width, rect.height) <= 1.5
                and not has_explicit_response_evidence(bbox)
            ):
                continue
            if any(
                native.bbox is not None
                and (
                    (
                        native.bbox[0] >= bbox[2] - 3
                        and native.bbox[0] - bbox[2] <= 240
                    )
                    or (
                        native.bbox[2] <= bbox[0] + 3
                        and bbox[0] - native.bbox[2] <= 240
                    )
                )
                and abs(
                    (native.bbox[1] + native.bbox[3]) / 2
                    - (bbox[1] + bbox[3]) / 2
                )
                <= max(14, bbox[3] - bbox[1])
                and _is_deterministic_choice_label(native, native_blocks)
                for native in native_blocks
            ):
                continue
            append_block(
                kind="field",
                bbox=bbox,
                block_label="form_field",
                confidence=1.0,
                response_area=True,
                discriminator=field_name,
            )

    for bbox, run_text, source_line_text in _underscore_run_bboxes(page, visibility_pixmap):
        response_bbox = [bbox[0] - 2, bbox[1] - 3, bbox[2] + 2, bbox[3] + 15]
        if _bbox_has_page_graphics(
            response_bbox,
            drawings=page_drawings,
            image_bboxes=page_image_bboxes,
        ):
            continue
        # The source line containing the underscore necessarily overlaps its
        # own response rectangle. Identify that exact extracted line rather
        # than exempting any overlapping text that happens to contain the
        # same underscore characters. Any second native line would be erased
        # during export, so it makes the destination unsafe.
        own_source_ids = {
            native.id
            for native in native_blocks
            if native.bbox is not None
            and native.text == source_line_text
            and native.bbox[0] - 1 <= bbox[0] <= native.bbox[2] + 1
            and native.bbox[0] - 1 <= bbox[2] <= native.bbox[2] + 1
            and native.bbox[1] - 1 <= bbox[1] <= native.bbox[3] + 1
            and native.bbox[1] - 1 <= bbox[3] <= native.bbox[3] + 1
        }
        if len(own_source_ids) != 1:
            continue
        own_source_id = next(iter(own_source_ids))
        own_source = next(native for native in native_blocks if native.id == own_source_id)
        if own_source.bbox is None or any(
            native.id != own_source_id
            and native.bbox is not None
            and _bbox_interiors_overlap(own_source.bbox, native.bbox)
            for native in native_blocks
        ):
            # Overprinted source lines are not an unambiguous blank, even if
            # the individual underscore run itself does not touch every
            # other line's expanded response rectangle.
            continue
        if any(
            native.bbox is not None
            and _bbox_interiors_overlap(response_bbox, native.bbox)
            and native.id not in own_source_ids
            for native in native_blocks
        ):
            continue
        append_block(
            kind="underscore",
            bbox=response_bbox,
            block_label="answer_line",
            confidence=0.97,
            response_area=True,
            discriminator=run_text,
        )

    # Vector rules are physical evidence only when nearby text makes their
    # response purpose explicit. Table grids, decorative dividers, and clipped
    # geometry remain non-writable candidates.
    seen: set[tuple[int, int, int]] = set()
    drawings = page.get_drawings()
    vector_geometry_available = _vector_geometry_within_budget(drawings)
    rectangle_bboxes, _horizontals, verticals = (
        _vector_rectangle_bboxes(drawings) if vector_geometry_available else ([], [], [])
    )
    if vector_geometry_available:
        existing = {
            tuple(round(value, 3) for value in bbox)
            for bbox in rectangle_bboxes
        }
        for frame in _closed_frame_bboxes(drawings):
            key = tuple(round(value, 3) for value in frame)
            if key not in existing:
                rectangle_bboxes.append(frame)
                existing.add(key)
    image_bboxes = [
        [float(value) for value in raw_block["bbox"]]
        for raw_block in page.get_text("dict", sort=True).get("blocks", [])
        if raw_block.get("type") == 1
        and isinstance(raw_block.get("bbox"), (list, tuple))
        and len(raw_block["bbox"]) == 4
    ]

    def line_signature(p0, p1) -> tuple[int, int, int]:
        raw_x0, raw_x1 = sorted((float(p0.x), float(p1.x)))
        return (round(raw_x0), round(raw_x1), round(float((p0.y + p1.y) / 2)))

    def line_touches_bbox(p0, p1, bbox: list[float], *, margin: float = 2.0) -> bool:
        x0, x1 = sorted((float(p0.x), float(p1.x)))
        y0, y1 = sorted((float(p0.y), float(p1.y)))
        return not (
            x1 < bbox[0] - margin
            or x0 > bbox[2] + margin
            or y1 < bbox[1] - margin
            or y0 > bbox[3] + margin
        )

    def line_marks_interior(p0, p1, bbox: list[float]) -> bool:
        inner = [bbox[0] + 2, bbox[1] + 2, bbox[2] - 2, bbox[3] - 2]
        return (
            inner[2] <= inner[0]
            or inner[3] <= inner[1]
            or line_touches_bbox(p0, p1, inner, margin=0)
        )

    def rectangle_marks_interior(rect, bbox: list[float]) -> bool:
        inner = [bbox[0] + 2, bbox[1] + 2, bbox[2] - 2, bbox[3] - 2]
        if inner[2] <= inner[0] or inner[3] <= inner[1]:
            return True
        return (
            any(
                inner[0] < x < inner[2] and rect.y0 < inner[3] and rect.y1 > inner[1]
                for x in (float(rect.x0), float(rect.x1))
            )
            or any(
                inner[1] < y < inner[3] and rect.x0 < inner[2] and rect.x1 > inner[0]
                for y in (float(rect.y0), float(rect.y1))
            )
        )

    def has_nontext_graphic_content(
        bbox: list[float],
        *,
        ignored_line: tuple[int, int, int] | None = None,
        ignore_candidate_outline: bool = False,
    ) -> bool:
        """Reject candidates drawn over actual image or vector content.

        A blank-looking rectangle can be a diagram panel. Native text alone
        cannot distinguish that case, so response authority requires an empty
        visual interior as well as response wording.
        """
        if any(_bbox_interiors_overlap(bbox, image_bbox) for image_bbox in image_bboxes):
            return True
        for drawing in drawings:
            rect = drawing.get("rect")
            if rect is None:
                continue
            drawing_bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
            fill = drawing.get("fill")
            # Paper-like fills are empty worksheet interiors, including white
            # checkbox/field backgrounds. Dark fills remain covering content.
            if (
                fill is not None
                and not _fill_is_paper_like(fill)
                and _bbox_interiors_overlap(bbox, drawing_bbox)
            ):
                return True
            for item in drawing.get("items", []):
                if not item:
                    continue
                if item[0] == "l":
                    p0, p1 = item[1], item[2]
                    if ignored_line is not None and line_signature(p0, p1) == ignored_line:
                        continue
                    if (
                        line_marks_interior(p0, p1, bbox)
                        if ignore_candidate_outline
                        else line_touches_bbox(p0, p1, bbox)
                    ):
                        return True
                elif item[0] == "re":
                    if rectangle_marks_interior(item[1], bbox):
                        return True
                elif (
                    not _fill_is_paper_like(fill)
                    and not (
                        ignore_candidate_outline
                        and _drawing_is_closed_frame(drawing)
                        and all(
                            abs(edge - other) <= 2
                            for edge, other in zip(bbox, drawing_bbox)
                        )
                    )
                    and _bbox_interiors_overlap(bbox, drawing_bbox)
                ):
                    # Curves and other path operators have no simple blank
                    # interior proof unless they are the candidate's own
                    # paper-like rounded frame.
                    return True
        return False

    def choice_label_for(bbox: list[float]) -> DocumentBlock | None:
        candidates = [
            native
            for native in native_blocks
            if native.bbox is not None
            and (
                (
                    native.bbox[0] >= bbox[2] - 3
                    and native.bbox[0] - bbox[2] <= 240
                )
                or (
                    native.bbox[2] <= bbox[0] + 3
                    and bbox[0] - native.bbox[2] <= 240
                )
            )
            and abs((native.bbox[1] + native.bbox[3]) / 2 - (bbox[1] + bbox[3]) / 2)
            <= max(14, bbox[3] - bbox[1])
            and _is_deterministic_choice_label(native, native_blocks)
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda native: (
                abs((native.bbox[1] + native.bbox[3]) / 2 - (bbox[1] + bbox[3]) / 2),
                min(abs(native.bbox[0] - bbox[2]), abs(bbox[0] - native.bbox[2])),
                native.reading_order,
                native.id,
            ),
        )

    def has_internal_grid(bbox: list[float]) -> bool:
        return any(
            bbox[0] + 3 < x < bbox[2] - 3
            and y0 <= bbox[1] + 2
            and y1 >= bbox[3] - 2
            for x, y0, y1 in verticals
        ) or any(
            bbox[1] + 3 < y < bbox[3] - 3
            and x0 <= bbox[0] + 2
            and x1 >= bbox[2] - 2
            for x0, x1, y in _horizontals
        )

    def is_grid_member(bbox: list[float]) -> bool:
        if has_internal_grid(bbox):
            return True
        # Line-encoded table cells share a boundary that continues past the
        # candidate's opposite edge. A writable rectangle normally has four
        # self-contained edges; a grid needs explicit cell semantics instead.
        if any(
            abs(x - edge_x) <= 2
            and y0 <= bbox[3] + 2
            and y1 >= bbox[1] - 2
            and (y0 < bbox[1] - 2 or y1 > bbox[3] + 2)
            for x, y0, y1 in verticals
            for edge_x in (bbox[0], bbox[2])
        ) or any(
            abs(y - edge_y) <= 2
            and x0 <= bbox[2] + 2
            and x1 >= bbox[0] - 2
            and (x0 < bbox[0] - 2 or x1 > bbox[2] + 2)
            for x0, x1, y in _horizontals
            for edge_y in (bbox[1], bbox[3])
        ):
            return True
        # Rectangle operators can encode each grid cell separately, without
        # exposing line segments. Adjacent boxes are still ambiguous until a
        # deterministic cell linker exists, so keep them non-writable.
        return any(
            other != bbox
            and (
                (
                    (abs(other[0] - bbox[2]) <= 2 or abs(other[2] - bbox[0]) <= 2)
                    and min(other[3], bbox[3]) - max(other[1], bbox[1]) > 8
                )
                or (
                    (abs(other[1] - bbox[3]) <= 2 or abs(other[3] - bbox[1]) <= 2)
                    and min(other[2], bbox[2]) - max(other[0], bbox[0]) > 8
                )
            )
            for other in rectangle_bboxes
        )

    def is_rectangle_edge(raw_x0: float, raw_x1: float, y: float) -> bool:
        # Rounded / inset frames often stroke a bottom rule slightly inside the
        # drawing bounds. Require substantial horizontal overlap with a known
        # frame rather than an exact full-span match.
        line_width = raw_x1 - raw_x0
        if line_width <= 0:
            return False
        for bbox in rectangle_bboxes:
            box_width = bbox[2] - bbox[0]
            if box_width <= 0:
                continue
            overlap = min(raw_x1, bbox[2]) - max(raw_x0, bbox[0])
            if overlap < 0.8 * min(line_width, box_width):
                continue
            if any(abs(y - edge_y) <= 2 for edge_y in (bbox[1], bbox[3])):
                return True
        return False

    def line_owned_by_writable_box(raw_x0: float, raw_x1: float, y: float) -> bool:
        """Reject answer-line minting for strokes that belong to a write box."""
        line_width = raw_x1 - raw_x0
        if line_width <= 0:
            return False
        return any(
            block.semantic_role == BlockSemanticRole.response_area
            and block.block_label in {"bounded_box", "writable_area", "form_field"}
            and block.bbox is not None
            and block.bbox[1] - 2 <= y <= block.bbox[3] + 2
            and (
                min(raw_x1, block.bbox[2]) - max(raw_x0, block.bbox[0])
                >= 0.8 * min(line_width, block.bbox[2] - block.bbox[0])
            )
            for block in blocks
        )

    def is_widget_appearance_rectangle(raw_bbox: list[float]) -> bool:
        # PyMuPDF exposes visible widget appearance streams through
        # page.get_drawings(). They duplicate the AcroForm rectangle but are
        # not independent worksheet evidence, so keep one canonical field.
        return any(
            all(abs(raw_edge - widget_edge) <= 2 for raw_edge, widget_edge in zip(raw_bbox, widget_bbox))
            for widget_bbox in widget_bboxes
        )

    for raw_bbox in rectangle_bboxes:
        width = raw_bbox[2] - raw_bbox[0]
        height = raw_bbox[3] - raw_bbox[1]
        if width <= 0 or height <= 0:
            continue
        if is_widget_appearance_rectangle(raw_bbox):
            continue
        choice_label = choice_label_for(raw_bbox)
        if (
            8 <= width <= 48
            and 8 <= height <= 48
            and max(width, height) / min(width, height) <= 1.5
            and choice_label is not None
            and not has_interior_text(raw_bbox)
            and not has_nontext_graphic_content(raw_bbox, ignore_candidate_outline=True)
            and _rectangle_outline_has_rendered_contrast(page, visibility_pixmap, raw_bbox)
        ):
            append_block(
                kind="checkbox",
                bbox=raw_bbox,
                block_label="checkbox",
                confidence=0.98,
                response_area=True,
                discriminator=choice_label.id,
            )
            continue
        box_like = width >= 24 and height >= 18
        explicit = has_explicit_response_evidence(raw_bbox)
        if (
            box_like
            and explicit
            and not has_interior_text(raw_bbox)
            and not has_nontext_graphic_content(raw_bbox, ignore_candidate_outline=True)
            and not is_grid_member(raw_bbox)
            and _rectangle_outline_has_rendered_contrast(page, visibility_pixmap, raw_bbox)
        ):
            append_block(
                kind="writable-area" if height >= 72 else "bounded-box",
                bbox=raw_bbox,
                block_label="writable_area" if height >= 72 else "bounded_box",
                confidence=0.97,
                response_area=True,
            )
        elif box_like:
            append_block(
                kind="box-candidate",
                bbox=raw_bbox,
                block_label="bounded_box_candidate",
                confidence=0.55,
                response_area=False,
            )

    if vector_geometry_available:
        vector_line_start = len(blocks)
        vector_rule_count = 0
        vector_rule_budget_exceeded = False
        for drawing in drawings:
            for item in drawing.get("items", []):
                if not item or item[0] != "l":
                    continue
                p0, p1 = item[1], item[2]
                if abs(p0.y - p1.y) > 2 or abs(p1.x - p0.x) < 24:
                    continue
                vector_rule_count += 1
                if vector_rule_count > _MAX_VECTOR_RULE_CANDIDATES:
                    vector_rule_budget_exceeded = True
                    break
                raw_x0, raw_x1 = sorted((float(p0.x), float(p1.x)))
                y = float((p0.y + p1.y) / 2)
                if is_rectangle_edge(raw_x0, raw_x1, y) or line_owned_by_writable_box(
                    raw_x0, raw_x1, y
                ):
                    continue
                signature = line_signature(p0, p1)
                if signature in seen:
                    continue
                seen.add(signature)
                intersections = sum(
                    raw_x0 - 2 <= x <= raw_x1 + 2 and vertical_y0 - 2 <= y <= vertical_y1 + 2
                    for x, vertical_y0, vertical_y1 in verticals
                )
                nearby_blocks = [
                    block
                    for block in native_blocks
                    if block.bbox is not None
                    and block.bbox[1] <= y
                    and y - block.bbox[3] <= 50
                    and (
                        # Ordinary overlap with the stroke's horizontal span.
                        (
                            block.bbox[2] >= raw_x0 - 24
                            and block.bbox[0] <= raw_x1 + 12
                        )
                        # Left-of-stroke field labels ("Answer:") often end a
                        # few points before an indented blank begins.
                        or (
                            block.text.rstrip().endswith(":")
                            and raw_x0 >= block.bbox[2] - 15
                            and raw_x0 - block.bbox[2] <= 180
                            and abs(y - ((block.bbox[1] + block.bbox[3]) / 2)) <= 24
                        )
                    )
                ]
                nearby_text = " ".join(block.text for block in nearby_blocks)
                # Minting remains broader than auto-approval. Answer:/Show your
                # work: labels, same-row colon fields ("Student name:"), and
                # nearby task prompts with response cues can surface a physical
                # line. Auto-approval still requires vetted student-write
                # evidence and cannot promote generic Name: metadata alone.
                # Choice-list pages are an exception: a choose/select prompt with
                # nearby A/B or 1/2 options must not mint a text answer_line from
                # the prompt cue alone, or decorative underlines become writable.
                explicit_response_label = any(
                    _is_explicit_response_label_text(block.text) for block in nearby_blocks
                )
                explicit_prompt_evidence = bool(
                    re.search(
                        r"\?|\b(answer|response|explain|describe|calculate|solve|"
                        r"write|record|why|what|how)\b",
                        nearby_text,
                        re.IGNORECASE,
                    )
                )
                explicit_field_label = any(
                    block.text.rstrip().endswith(":")
                    and raw_x0 >= block.bbox[2] - 15
                    and abs(y - ((block.bbox[1] + block.bbox[3]) / 2)) <= 16
                    for block in nearby_blocks
                    if block.bbox is not None
                )
                choice_list_context = bool(_CHOICE_PROMPT_CUE.search(nearby_text)) and any(
                    _CHOICE_TEXT.match(block.text) for block in nearby_blocks
                )
                # Ignore alphabetic choice labels in the gap check so a later
                # option row cannot demote a real answer blank beneath a task
                # prompt. Numbered prompts themselves must still set the gap.
                gaps_above = [
                    y - block.bbox[3]
                    for block in nearby_blocks
                    if block.bbox is not None
                    and block.bbox[3] <= y + 1
                    and not _ALPHABETIC_CHOICE_TEXT.match(block.text)
                ]
                prompt_cue_gap_ok = not gaps_above or min(gaps_above) >= 20
                raw_bbox = [raw_x0, y - 5, raw_x1, y + 19]
                # Only text that reaches the stroke band can poison an answer
                # line. Labels for the next field often sit just below the
                # expanded write box and must not demote a valid blank.
                overlaps_source_text = any(
                    native.bbox is not None
                    and native.bbox[1] <= y + 2
                    and _bbox_interiors_overlap(raw_bbox, native.bbox)
                    for native in native_blocks
                )
                safe_line = (
                    intersections < 2
                    and _vector_segment_has_rendered_contrast(
                        page,
                        visibility_pixmap,
                        (raw_x0, y),
                        (raw_x1, y),
                    )
                    and (
                        explicit_response_label
                        or explicit_field_label
                        or (
                            explicit_prompt_evidence
                            and not choice_list_context
                            and prompt_cue_gap_ok
                        )
                    )
                    # Worksheets often use a 2–3pt answer rule for visual
                    # accessibility. With local response wording or a same-row
                    # field label, empty interior, and rendered-contrast proof,
                    # that stroke remains a physical destination; heavier
                    # divider bars remain side-panel-only.
                    and float(drawing.get("width") or 1) <= 4.0
                    and not has_nontext_graphic_content(raw_bbox, ignored_line=signature)
                )
                append_block(
                    kind="line",
                    bbox=raw_bbox,
                    # Decorative dividers without local prompt/field evidence
                    # stay non-authoritative horizontal_rule candidates so
                    # semantic/UI flows can still see them and fail closed.
                    block_label=(
                        "answer_line"
                        if safe_line and not overlaps_source_text
                        else "horizontal_rule_candidate"
                    ),
                    confidence=0.92 if safe_line and not overlaps_source_text else 0.55,
                    response_area=safe_line and not overlaps_source_text,
                )
            if vector_rule_budget_exceeded:
                break
        if vector_rule_budget_exceeded:
            # A bounded subset would make arbitrary drawing order determine
            # write authority, so discard every raw line candidate on page.
            del blocks[vector_line_start:]
    return [
        block.model_copy(update={"reading_order": start_order + index})
        for index, block in enumerate(
            sorted(
                blocks,
                key=lambda block: (
                    block.bbox[1] if block.bbox is not None else float("inf"),
                    block.bbox[0] if block.bbox is not None else float("inf"),
                    block.bbox[3] if block.bbox is not None else float("inf"),
                    block.bbox[2] if block.bbox is not None else float("inf"),
                    block.id,
                ),
            )
        )
    ]


def current_pdf_page_evidence(
    page: fitz.Page,
    page_index: int,
) -> tuple[list[DocumentBlock], list[DocumentBlock]]:
    """Rebuild native and physical evidence from the source page alone.

    Export uses this deterministic routine to authenticate a persisted
    canonical response destination against the PDF it is about to modify.
    """
    visibility_pixmap = _page_visibility_pixmap(page)
    drawings = page.get_drawings()
    image_bboxes = [
        [float(value) for value in raw_block["bbox"]]
        for raw_block in page.get_text("dict", sort=True).get("blocks", [])
        if raw_block.get("type") == 1
        and isinstance(raw_block.get("bbox"), (list, tuple))
        and len(raw_block["bbox"]) == 4
    ]
    native = _native_blocks(
        page,
        page_index,
        visibility_pixmap=visibility_pixmap,
        drawings=drawings,
        image_bboxes=image_bboxes,
    )
    return native, _physical_response_blocks(
        page,
        page_index,
        len(native),
        native,
        visibility_pixmap=visibility_pixmap,
    )


def _paddle_blocks(
    result,
    start_order: int = 0,
    *,
    include_geometry: bool = True,
) -> list[DocumentBlock]:
    blocks = []
    for index, item in enumerate(result.blocks):
        source_id = item.source_id or str(index)
        blocks.append(
            DocumentBlock(
                id=f"page-{result.page_index}-paddle-{source_id}",
                page_index=result.page_index,
                reading_order=start_order + item.reading_order,
                text=item.text,
                block_label=item.label,
                bbox=list(item.bbox) if include_geometry else None,
                polygon=([list(point) for point in item.polygon] if item.polygon else None)
                if include_geometry
                else None,
                confidence=item.confidence,
                source=SourceKind.paddleocr,
            )
        )
    return blocks


def _page_is_visually_structured(page: fitz.Page) -> bool:
    page_area = max(float(page.rect.width * page.rect.height), 1.0)
    image_area = 0.0
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox") or []
        if len(bbox) == 4:
            image_area += max(0.0, float(bbox[2] - bbox[0])) * max(0.0, float(bbox[3] - bbox[1]))
    if image_area / page_area >= 0.08 or page.first_widget is not None:
        return True

    horizontal = 0
    vertical = 0
    form_rectangles = 0
    vector_items = 0
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if not item:
                continue
            if item[0] in {"l", "re"}:
                vector_items += 1
                if vector_items > _MAX_VECTOR_GEOMETRY_ITEMS:
                    return True
            if item[0] == "l":
                p0, p1 = item[1], item[2]
                if abs(p0.y - p1.y) <= 2 and abs(p1.x - p0.x) >= 80:
                    horizontal += 1
                elif abs(p0.x - p1.x) <= 2 and abs(p1.y - p0.y) >= 30:
                    vertical += 1
            elif item[0] == "re":
                rect = item[1]
                if rect.width >= 80 and rect.height >= 18:
                    form_rectangles += 1
            if (horizontal >= 2 and vertical >= 2) or form_rectangles >= 3:
                return True
    return (horizontal >= 2 and vertical >= 2) or form_rectangles >= 3


def _render_page_png(page: fitz.Page, dpi: int = 100) -> bytes:
    scale = dpi / 72.0
    return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png")


def _page_context(pages_blocks: list[list[DocumentBlock]], page_index: int) -> str:
    sections = []
    for index in range(max(0, page_index - 1), min(len(pages_blocks), page_index + 2)):
        text = " ".join(block.text for block in pages_blocks[index] if block.text).strip()
        sections.append(f"page {index}: {text[:700]}")
    return "\n".join(sections)


def _response_matches_prompt(
    response: DocumentBlock,
    prompt_blocks: list[DocumentBlock],
    all_blocks: list[DocumentBlock],
    *,
    anchor_page_index: int,
    selected_response_ids: set[str] | None = None,
) -> bool:
    """Accept only geometry relationships that are unambiguous without a model.

    A semantic model may select source IDs, but it cannot make a response area
    belong to a prompt by assertion alone. Cross-page continuations and
    competing numbered prompts remain side-panel-only until explicitly
    reviewed.
    """
    if response.bbox is None or response.page_index != anchor_page_index:
        return False
    if not prompt_blocks or any(
        prompt.bbox is None or prompt.page_index != anchor_page_index
        for prompt in prompt_blocks
    ):
        return False
    selected_response_ids = selected_response_ids or {response.id}
    if any(_prompt_looks_like_a_numeric_choice(prompt, all_blocks) for prompt in prompt_blocks):
        return False
    overlaps_prompt_text = any(
        _bbox_interiors_overlap(prompt.bbox, response.bbox)
        for prompt in prompt_blocks
        if prompt.bbox is not None
    )
    if overlaps_prompt_text:
        # An explicit underscore run lives inside the source text line by
        # definition; a vector underline crossing prompt text does not. An
        # underscore in a heading or teacher label is still not a student
        # task, so retain the same deterministic task-shape requirement.
        if "-underscore-" in response.id:
            if not any(_is_task_shaped_prompt(prompt.text) for prompt in prompt_blocks):
                return False
            # A model cannot select only one blank from a source line that
            # visibly contains multiple physical destinations. The other
            # same-line response evidence must remain side-panel-only unless
            # an explicit deterministic multi-blank association exists.
            return not any(
                block.id not in selected_response_ids
                and block.page_index == anchor_page_index
                and block.source == SourceKind.pdf_geometry
                and block.semantic_role == BlockSemanticRole.response_area
                and block.bbox is not None
                and any(
                    prompt.bbox is not None
                    and _bbox_interiors_overlap(block.bbox, prompt.bbox)
                    for prompt in prompt_blocks
                )
                for block in all_blocks
            )
        return False

    prompt_ids = {prompt.id for prompt in prompt_blocks}
    prompt_top = min(prompt.bbox[1] for prompt in prompt_blocks if prompt.bbox is not None)
    prompt_bottom = max(prompt.bbox[3] for prompt in prompt_blocks if prompt.bbox is not None)

    # Structured checkbox controls commonly sit left of choice text and left of
    # the prompt card. Horizontal overlap with the prompt is therefore not a
    # reliable linker. A deterministic same-row choice label below the prompt
    # is enough, provided no intervening task-shaped prompt appears.
    if response.block_label == "checkbox":
        choice_source = _choice_source_for_checkbox(response, all_blocks)
        if choice_source is None or response.bbox[1] < prompt_bottom - 4:
            return False
        for block in all_blocks:
            if (
                block.id in prompt_ids
                or block.page_index != anchor_page_index
                or block.source != SourceKind.native_pdf
                or block.bbox is None
                or not block.text.strip()
                or not _is_task_shaped_prompt(block.text)
                or _is_deterministic_choice_label(block, all_blocks)
            ):
                continue
            if prompt_bottom - 2 <= block.bbox[1] <= response.bbox[3] + 2:
                return False
        return True

    def horizontal_overlap(first: list[float], second: list[float]) -> float:
        return min(first[2], second[2]) - max(first[0], second[0])

    def is_local_explicit_response_label(block: DocumentBlock) -> bool:
        if (
            block.source != SourceKind.native_pdf
            or block.page_index != anchor_page_index
            or block.bbox is None
            or not _is_explicit_response_label_text(block.text)
        ):
            return False
        same_row_left = (
            block.bbox[2] <= response.bbox[0] + 12
            and response.bbox[0] - block.bbox[2] <= 180
            and abs(
                (block.bbox[1] + block.bbox[3]) / 2
                - (response.bbox[1] + response.bbox[3]) / 2
            )
            <= 20
        )
        directly_above = (
            block.bbox[3] <= response.bbox[1] + 8
            and response.bbox[1] - block.bbox[3] <= 32
            and block.bbox[2] >= response.bbox[0] - 24
            and block.bbox[0] <= response.bbox[2] + 24
        )
        return same_row_left or directly_above

    local_explicit_response_label = any(
        is_local_explicit_response_label(block) for block in all_blocks
    )

    same_row_field = any(
        prompt.bbox is not None
        and prompt.text.rstrip().endswith(":")
        and response.bbox[0] >= prompt.bbox[2] - 15
        and abs((response.bbox[1] + response.bbox[3]) / 2 - (prompt.bbox[1] + prompt.bbox[3]) / 2)
        <= 20
        for prompt in prompt_blocks
    )
    if same_row_field:
        # A same-row form field is only obvious when no other source text
        # occupies the horizontal corridor between its selected label and the
        # field. Without this, a model can skip a neighboring prompt.
        prompt_right = max(prompt.bbox[2] for prompt in prompt_blocks if prompt.bbox is not None)
        corridor = [
            min(prompt_right, response.bbox[0]),
            min(prompt_top, response.bbox[1]) - 2,
            max(prompt_right, response.bbox[0]),
            max(prompt_bottom, response.bbox[3]) + 2,
        ]
        for block in all_blocks:
            if (
                block.id in prompt_ids
                or block.page_index != anchor_page_index
                or block.source != SourceKind.native_pdf
                or block.bbox is None
                or not block.text.strip()
            ):
                continue
            if _bbox_interiors_overlap(corridor, block.bbox):
                return False
        return True
    if response.bbox[1] < prompt_bottom - 4:
        return False

    has_prompt_horizontal_overlap = any(
        horizontal_overlap(prompt.bbox, response.bbox) >= 8
        for prompt in prompt_blocks
        if prompt.bbox is not None
    )
    if not has_prompt_horizontal_overlap and not local_explicit_response_label:
        # Separate columns are ambiguous without an explicit column linker.
        return False
    if not has_prompt_horizontal_overlap and any(
        block.id not in prompt_ids
        and block.source == SourceKind.native_pdf
        and block.page_index == anchor_page_index
        and block.bbox is not None
        and _is_task_shaped_prompt(block.text)
        and not _is_deterministic_choice_label(block, all_blocks)
        and block.bbox[3] <= response.bbox[1] + 2
        for block in all_blocks
    ):
        # A right-aligned label is an explicit local link, but it cannot pick
        # among multiple preceding numbered prompts in another column.
        return False

    response_has_explicit_extended_label = _response_link_role(
        response,
        prompt_blocks,
        all_blocks,
    ) in {TaskResponseRole.explanation, TaskResponseRole.show_work}

    def is_local_response_label(block: DocumentBlock) -> bool:
        if block.bbox is None:
            return False
        return (
            (
                block.bbox[2] <= response.bbox[0] + 12
                and response.bbox[0] - block.bbox[2] <= 180
                and abs(
                    (block.bbox[1] + block.bbox[3]) / 2
                    - (response.bbox[1] + response.bbox[3]) / 2
                )
                <= 20
            )
            or (
                block.bbox[3] <= response.bbox[1] + 8
                and response.bbox[1] - block.bbox[3] <= 32
                and block.bbox[2] >= response.bbox[0] - 24
                and block.bbox[0] <= response.bbox[2] + 24
            )
        )

    for block in all_blocks:
        if (
            block.id in prompt_ids
            or block.page_index != anchor_page_index
            or block.source != SourceKind.native_pdf
            or block.bbox is None
            or not block.text.strip()
            or _is_deterministic_choice_label(block, all_blocks)
            or _is_explicit_response_label_text(block.text)
            or not (_is_task_shaped_prompt(block.text) or _TASK_INSTRUCTION_START.match(block.text))
        ):
            continue
        if block.bbox[3] < prompt_top - 2 or block.bbox[1] > response.bbox[3] + 2:
            continue
        if horizontal_overlap(block.bbox, response.bbox) < 8 and not is_local_response_label(block):
            continue
        if (
            response_has_explicit_extended_label
            and is_local_response_label(block)
            and (_SHOW_WORK_CUE.search(block.text) or _EXPLANATION_CUE.search(block.text))
        ):
            continue
        # A competing numbered or imperative task can share a row with the
        # selected prompt or overlap a field's top. Do not let model-selected
        # IDs silently choose between those tasks.
        return False

    for block in all_blocks:
        if (
            block.id in prompt_ids
            or block.page_index != anchor_page_index
            or block.source != SourceKind.native_pdf
            or block.bbox is None
            or not block.text.strip()
        ):
            continue
        # Include source text that overlaps the top of a field. Otherwise an
        # unselected imperative such as "Calculate the second result:" can
        # sit in the field's label corridor and be skipped solely because the
        # widget begins a few points above the baseline.
        if block.bbox[1] < prompt_bottom - 2 or block.bbox[1] > response.bbox[3] + 2:
            continue
        # Option labels sit between a multiple-choice prompt and its checkbox;
        # they are source evidence for a choice, not a competing task. A
        # later explanation/show-work field can cross those rows only when a
        # local explicit label names that distinct destination.
        if _is_deterministic_choice_label(block, all_blocks) and (
            response.block_label == "checkbox" or response_has_explicit_extended_label
        ):
            continue
        if (
            response_has_explicit_extended_label
            and is_local_response_label(block)
            and (_SHOW_WORK_CUE.search(block.text) or _EXPLANATION_CUE.search(block.text))
        ):
            continue
        # A selected prompt must account for all intervening substantive text.
        # The only permitted unselected text is an explicit response label
        # immediately naming the destination (for example, "Answer:").
        # Otherwise a model could leap from one prompt over an unnumbered
        # second prompt to a later answer line.
        if not _is_explicit_response_label_text(block.text):
            return False

    for block in all_blocks:
        if (
            block.id in prompt_ids
            or block.page_index != anchor_page_index
            or block.source != SourceKind.native_pdf
            or block.bbox is None
            or not block.text.strip()
            or not _is_task_shaped_prompt(block.text)
            or _is_deterministic_choice_label(block, all_blocks)
        ):
            continue
        if block.bbox[3] < prompt_top - 2 or block.bbox[1] > response.bbox[1] + 2:
            continue
        if horizontal_overlap(block.bbox, response.bbox) >= 8:
            # Same-row or overlapping-column task prompts make the response
            # relationship ambiguous, even when neither prompt lies wholly
            # in the vertical gap checked above.
            return False

    for block in all_blocks:
        if (
            block.id in selected_response_ids
            or block.page_index != anchor_page_index
            or block.source != SourceKind.pdf_geometry
            or block.semantic_role != BlockSemanticRole.response_area
            or block.bbox is None
        ):
            continue
        if block.bbox[1] < prompt_bottom - 4 or block.bbox[1] >= response.bbox[1] - 2:
            continue
        if horizontal_overlap(block.bbox, response.bbox) >= 8:
            # Skipping an earlier blank is not an obvious association.
            return False
    return True


def _choice_source_for_checkbox(
    checkbox: DocumentBlock,
    blocks: list[DocumentBlock],
) -> DocumentBlock | None:
    if checkbox.bbox is None:
        return None
    candidates = [
        block
        for block in blocks
        if block.source == SourceKind.native_pdf
        and block.page_index == checkbox.page_index
        and block.bbox is not None
        and (
            (
                block.bbox[0] >= checkbox.bbox[2] - 3
                and block.bbox[0] - checkbox.bbox[2] <= 240
            )
            or (
                block.bbox[2] <= checkbox.bbox[0] + 3
                and checkbox.bbox[0] - block.bbox[2] <= 240
            )
        )
        and abs((block.bbox[1] + block.bbox[3]) / 2 - (checkbox.bbox[1] + checkbox.bbox[3]) / 2)
        <= max(14, checkbox.bbox[3] - checkbox.bbox[1])
        and _is_deterministic_choice_label(block, blocks)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda block: (
            abs((block.bbox[1] + block.bbox[3]) / 2 - (checkbox.bbox[1] + checkbox.bbox[3]) / 2),
            min(
                abs(block.bbox[0] - checkbox.bbox[2]),
                abs(checkbox.bbox[0] - block.bbox[2]),
            ),
            block.reading_order,
            block.id,
        ),
    )


def _response_link_role(
    response: DocumentBlock,
    prompt_blocks: list[DocumentBlock],
    blocks: list[DocumentBlock],
) -> TaskResponseRole:
    """Derive explicit multi-region roles from local source text only."""
    if response.block_label == "checkbox":
        return TaskResponseRole.choice
    if response.bbox is None:
        return TaskResponseRole.other
    prompt_ids = {prompt.id for prompt in prompt_blocks}
    labels = [
        block
        for block in blocks
        if block.id not in prompt_ids
        and block.source == SourceKind.native_pdf
        and block.page_index == response.page_index
        and block.bbox is not None
        and block.text.strip()
        and block.text.rstrip().endswith(":")
        and (
            (
                block.bbox[2] <= response.bbox[0] + 12
                and response.bbox[0] - block.bbox[2] <= 180
                and abs((block.bbox[1] + block.bbox[3]) / 2 - (response.bbox[1] + response.bbox[3]) / 2)
                <= 20
            )
            or (
                block.bbox[3] <= response.bbox[1] + 8
                and response.bbox[1] - block.bbox[3] <= 32
                and block.bbox[2] >= response.bbox[0] - 24
                and block.bbox[0] <= response.bbox[2] + 24
            )
        )
    ]
    label_text = " ".join(block.text for block in labels)
    if _SHOW_WORK_CUE.search(label_text):
        return TaskResponseRole.show_work
    if _EXPLANATION_CUE.search(label_text):
        return TaskResponseRole.explanation
    return TaskResponseRole.answer


def selected_response_blocks_are_distinct(
    response_blocks: list[DocumentBlock],
    prompt_blocks: list[DocumentBlock],
    all_blocks: list[DocumentBlock],
) -> bool:
    """Require explicit source labels for multiple non-choice destinations."""
    if len(response_blocks) <= 1:
        return True
    roles = [
        _response_link_role(block, prompt_blocks, all_blocks)
        for block in response_blocks
    ]
    if all(role == TaskResponseRole.choice for role in roles):
        return True
    if any(role == TaskResponseRole.choice for role in roles):
        # Checkboxes are structured selection evidence, not a text write
        # target. Preserve a separately and explicitly labelled explanation
        # or show-work response without pretending the selection itself can
        # be rendered onto the original worksheet. An "Answer:" line under a
        # choice task is treated as the explanation destination when the
        # local label is explanation-shaped.
        return (
            all(
                role
                in {
                    TaskResponseRole.choice,
                    TaskResponseRole.explanation,
                    TaskResponseRole.show_work,
                    TaskResponseRole.answer,
                }
                for role in roles
            )
            and roles.count(TaskResponseRole.answer) <= 1
            and (
                any(
                    role in {TaskResponseRole.explanation, TaskResponseRole.show_work}
                    for role in roles
                )
                or roles.count(TaskResponseRole.answer) == 1
            )
        )
    return (
        roles.count(TaskResponseRole.answer) == 1
        and all(
            role in {TaskResponseRole.answer, TaskResponseRole.explanation, TaskResponseRole.show_work}
            for role in roles
        )
        and any(role in {TaskResponseRole.explanation, TaskResponseRole.show_work} for role in roles)
    )


def _prompt_blocks_describe_at_most_one_task(prompt_blocks: list[DocumentBlock]) -> bool:
    """Recognize one source prompt, including a tightly wrapped continuation.

    The first line must be a numbered/question task or an unnumbered
    sentence-case worksheet prompt. Later lines can continue that line only if
    they remain in the same reading column, have no gap, and do not
    independently begin an imperative task. This keeps a model from selecting a
    second prompt simply to bypass the interposed-text gate.
    """
    if len(prompt_blocks) == 1:
        return not _prompt_text_has_competing_instruction(prompt_blocks[0].text)
    first = prompt_blocks[0]
    if (
        first.bbox is None
        or first.source != SourceKind.native_pdf
        or not (
            _is_task_shaped_prompt(first.text)
            or _is_unnumbered_student_prompt_anchor(first.text)
        )
    ):
        return False
    previous = first
    for continuation in prompt_blocks[1:]:
        if not _is_tight_prompt_continuation(previous, continuation, first=first):
            return False
        previous = continuation
    return True


def _build_tasks(
    blocks: list[DocumentBlock],
    semantic_results,
    *,
    review_mode: str,
) -> tuple[list[DocumentTask], list[DocumentResponseRegion]]:
    """Materialize semantic selections without merging physical response areas."""
    block_by_id = {block.id: block for block in blocks}

    def physical_order(block: DocumentBlock) -> tuple[int, float, float, float, float, int, str]:
        bbox = block.bbox or [float("inf"), float("inf"), float("inf"), float("inf")]
        return (
            block.page_index,
            bbox[1],
            bbox[0],
            bbox[3],
            bbox[2],
            block.reading_order,
            block.id,
        )

    def ordered_blocks(block_ids: list[str], label: str) -> list[DocumentBlock]:
        if len(block_ids) != len(set(block_ids)):
            raise ValueError(f"semantic task has duplicate {label} block IDs")
        return sorted((block_by_id[block_id] for block_id in block_ids), key=physical_order)

    tasks: list[DocumentTask] = []
    response_regions: list[DocumentResponseRegion] = []
    claimed_response_block_ids: set[str] = set()
    claimed_response_blocks: list[DocumentBlock] = []
    task_ids: set[str] = set()

    def candidate_sort_key(item) -> tuple[int, float, float, float, float, int, str, str]:
        result, candidate = item
        prompt_blocks = ordered_blocks(candidate.prompt_block_ids, "prompt")
        prompt_text = source_prompt_text(prompt_blocks)
        if not prompt_text:
            raise ValueError("semantic task selected no source prompt text")
        first_prompt = prompt_blocks[0]
        return (*physical_order(first_prompt), stable_task_id(result.page_index, [block.id for block in prompt_blocks], prompt_text))

    semantic_candidates = [
        (result, candidate)
        for result in semantic_results
        if result.page_role in {PageRole.student_worksheet, PageRole.mixed}
        for candidate in result.tasks
    ]
    for result, candidate in sorted(semantic_candidates, key=candidate_sort_key):
        prompt_blocks = _expand_wrapped_prompt_blocks(
            ordered_blocks(candidate.prompt_block_ids, "prompt"),
            blocks,
        )
        response_blocks = ordered_blocks(candidate.response_block_ids, "response")
        duplicate_response_sources = [
            block.id for block in response_blocks if block.id in claimed_response_block_ids
        ]
        if duplicate_response_sources:
            raise ValueError("semantic tasks selected the same physical response block")
        candidate_response_blocks: list[DocumentBlock] = []
        for block in response_blocks:
            if block.bbox is None:
                continue
            if any(
                block.page_index == claimed.page_index
                and claimed.bbox is not None
                and max(block.bbox[0], claimed.bbox[0]) < min(block.bbox[2], claimed.bbox[2])
                and max(block.bbox[1], claimed.bbox[1]) < min(block.bbox[3], claimed.bbox[3])
                for claimed in [*claimed_response_blocks, *candidate_response_blocks]
            ):
                raise ValueError("semantic tasks selected overlapping physical response blocks")
            candidate_response_blocks.append(block)
        prompt_blocks_describe_one_task = _prompt_blocks_describe_at_most_one_task(prompt_blocks)
        relationship_unambiguous = prompt_blocks_describe_one_task and all(
            _response_matches_prompt(
                block,
                prompt_blocks,
                blocks,
                anchor_page_index=result.page_index,
                selected_response_ids={candidate_block.id for candidate_block in response_blocks},
            )
            for block in response_blocks
        ) and selected_response_blocks_are_distinct(response_blocks, prompt_blocks, blocks)
        materialized_response_blocks = response_blocks if relationship_unambiguous else []
        prompt_is_task_shaped = (
            prompt_blocks_describe_one_task
            and _is_task_shaped_prompt(prompt_blocks[0].text)
        )
        prompt_evidence_is_native = all(block.source == SourceKind.native_pdf for block in prompt_blocks)
        eligible_response_blocks = [
            block
            for block in materialized_response_blocks
            if block.bbox is not None
            and block.source == SourceKind.pdf_geometry
            and block.semantic_role == BlockSemanticRole.response_area
            and block.block_label in _AUTO_APPROVABLE_RESPONSE_LABELS
            and block.confidence >= 0.85
        ]
        confidence = min(candidate.confidence, result.confidence)
        can_auto_approve = (
            config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE
            and review_mode == "direct"
            and result.page_role == PageRole.student_worksheet
            and confidence >= config.TASK_AUTO_APPROVE_CONFIDENCE
            and prompt_is_task_shaped
            and prompt_evidence_is_native
            and bool(eligible_response_blocks)
            and len(eligible_response_blocks) == len(materialized_response_blocks)
            and all(
                block.confidence >= config.ANSWER_REGION_AUTO_APPROVE_CONFIDENCE
                for block in eligible_response_blocks
            )
        )
        review_status = ReviewStatus.auto_approved if can_auto_approve else ReviewStatus.needs_review
        prompt_block_ids = [block.id for block in prompt_blocks]
        prompt_text = source_prompt_text(prompt_blocks)
        if not prompt_text:
            raise ValueError("semantic task selected no source prompt text")
        task_id = stable_task_id(
            result.page_index,
            prompt_block_ids,
            prompt_text,
        )
        if task_id in task_ids:
            raise ValueError("semantic tasks resolved to the same canonical task identity")
        task_ids.add(task_id)
        claimed_response_block_ids.update(block.id for block in response_blocks)
        claimed_response_blocks.extend(candidate_response_blocks)
        response_links: list[TaskResponseLink] = []
        task_regions: list[DocumentResponseRegion] = []
        choices: list[DocumentChoice] = []
        for block in materialized_response_blocks:
            if block.bbox is None:
                continue
            role = _response_link_role(block, prompt_blocks, blocks)
            choice_id: str | None = None
            if role == TaskResponseRole.choice:
                choice_source = _choice_source_for_checkbox(block, blocks)
                if choice_source is None:
                    # A checkbox without a deterministic source label cannot
                    # form a choice relation or a writable destination.
                    continue
                choice_text = source_prompt_text([choice_source])
                choice_id = "choice-" + hashlib.sha256(
                    f"{task_id}:{choice_source.id}".encode("utf-8")
                ).hexdigest()[:16]
                choices.append(
                    DocumentChoice(
                        id=choice_id,
                        order=len(choices),
                        text=choice_text,
                        source_block_ids=[choice_source.id],
                    )
                )
            region_type = {
                "answer_line": ResponseRegionType.answer_line,
                "form_field": ResponseRegionType.form_field,
                "checkbox": ResponseRegionType.checkbox,
                "bounded_box": ResponseRegionType.bounded_box,
                "writable_area": ResponseRegionType.writable_area,
            }.get(block.block_label, ResponseRegionType.unknown)
            safety = (
                ResponseSafety.approved
                if can_auto_approve and block in eligible_response_blocks
                else (
                    ResponseSafety.needs_review
                    if block.block_label in _SAFE_RESPONSE_LABELS
                    else ResponseSafety.unsafe
                )
            )
            region_id = stable_response_region_id(task_id, [block.id])
            region = DocumentResponseRegion(
                id=region_id,
                page_index=block.page_index,
                bbox=block.bbox,
                region_type=region_type,
                response_type=candidate.response_type,
                safety=safety,
                confidence=min(confidence, block.confidence),
                source_block_ids=[block.id],
            )
            response_regions.append(region)
            task_regions.append(region)
            response_links.append(
                TaskResponseLink(
                    response_region_id=region_id,
                    role=role,
                    order=len(response_links),
                    choice_id=choice_id,
                )
            )
        tasks.append(
            DocumentTask(
                id=task_id,
                legacy_question_id=len(tasks) + 1,
                order=len(tasks),
                label=candidate.label,
                prompt_text=prompt_text,
                anchor_page_index=result.page_index,
                page_role=result.page_role,
                prompt_block_ids=prompt_block_ids,
                choices=choices,
                response_links=response_links,
                side_panel_fallback=not relationship_unambiguous
                or not response_links
                or not any(link.role == TaskResponseRole.answer for link in response_links)
                or any(region.safety != ResponseSafety.approved for region in task_regions),
                response_type=candidate.response_type,
                confidence=confidence,
                review_status=review_status,
            )
        )
    return tasks, response_regions


def parse_document(
    pdf_bytes: bytes,
    *,
    ocr_adapter: OCRAdapter | None = None,
    semantic_classifier: SemanticClassifier | None = None,
    review_mode: str = "direct",
    paddle_all_pages: bool = False,
) -> IntermediateDocument:
    """Extract physical blocks, classify semantics, and build review-safe tasks."""
    if review_mode not in {"direct", "teacher"}:
        raise ValueError("review_mode must be direct or teacher")
    started = time.perf_counter()
    ocr_adapter = ocr_adapter or get_ocr_adapter()
    semantic_classifier = semantic_classifier or NullSemanticClassifier()
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if document.page_count > config.MAX_PDF_PAGES:
            raise ValueError("PDF exceeds the maximum page count")
        pages: list[DocumentPage] = []
        pages_blocks: list[list[DocumentBlock]] = []
        source_nonstudent_write_pages: set[int] = set()
        warnings: list[str] = []

        for page_index, page in enumerate(document):
            display_transform_required = _page_requires_display_transform(page)
            page_width, page_height = _page_extraction_dimensions(page)
            if page_has_nonstudent_write_cue_in_source(page):
                source_nonstudent_write_pages.add(page_index)
            native, physical = current_pdf_page_evidence(page, page_index)
            native_reliable = has_reliable_native_page_text(native)
            # Physical IDs and reading order are derived before optional OCR
            # so an OCR layout block can never renumber native geometry.
            page_blocks = [*native, *physical]
            page_warnings: list[str] = []
            paddle_block_count = 0
            status = ParseStatus.parsed
            ocr_required = not native_reliable
            should_run_paddle = paddle_all_pages or ocr_required or (
                not isinstance(ocr_adapter, NullOCRAdapter) and _page_is_visually_structured(page)
            )
            if should_run_paddle:
                result = ocr_adapter.extract_page(pdf_bytes, page_index)
                page_warnings.extend(result.warnings)
                # Paddle works from a rendered display page. When the source
                # PDF needs a display transform, retaining its display-frame
                # geometry alongside native extraction geometry would invent a
                # relationship between two coordinate systems. Keep OCR text
                # as semantic evidence but remove its geometry and force any
                # response selection to the side panel.
                paddle = _paddle_blocks(
                    result,
                    start_order=len(page_blocks),
                    include_geometry=not display_transform_required,
                )
                paddle_block_count = len(paddle)
                if display_transform_required and paddle:
                    page_warnings.append("paddle_geometry_omitted_for_transformed_page")
                if native_reliable:
                    # Native text remains the text source of truth. Paddle contributes
                    # non-text layout regions (tables/images/etc.) and provenance.
                    page_blocks.extend(
                        block
                        for block in paddle
                        if block.block_label not in {"text", "ocr_text", "paragraph_title", "doc_title"}
                    )
                else:
                    page_blocks.extend(paddle)
                if result.status == "failed":
                    status = ParseStatus.requires_ocr if ocr_required else ParseStatus.low_confidence
                elif result.status == "low_confidence":
                    status = ParseStatus.low_confidence
                elif paddle:
                    ocr_required = False
            if ocr_required and not any(block.source == SourceKind.paddleocr for block in page_blocks):
                status = ParseStatus.requires_ocr
                if "requires_ocr" not in page_warnings:
                    page_warnings.append("requires_ocr")

            page_blocks, geometry_sanitized = _sanitize_blocks_to_page(
                page_blocks,
                width=page_width,
                height=page_height,
            )
            if geometry_sanitized or any(
                block.block_label == "clipped_response_candidate" for block in physical
            ):
                page_warnings.append("extraction_geometry_clipped_or_omitted")
            page_model = DocumentPage(
                page_index=page_index,
                # Preserve the unrotated extraction frame (including crop and
                # /UserUnit scaling), rather than mixing it with rotated page
                # display bounds. Any page requiring a display transform is
                # deliberately side-panel-only until that transform exists.
                width_points=page_width,
                height_points=page_height,
                rotation=int(page.rotation) % 360,
                display_transform_required=display_transform_required,
                native_text_exists=native_reliable,
                ocr_required=ocr_required,
                extraction_status=status,
                paddle_block_count=paddle_block_count,
                block_ids=[block.id for block in page_blocks],
                warnings=page_warnings,
            )
            pages.append(page_model)
            pages_blocks.append(page_blocks)
            warnings.extend(f"page_{page_index}:{warning}" for warning in page_warnings)

        semantic_results = []
        for page_index, page_model in enumerate(pages):
            page_blocks = pages_blocks[page_index]
            use_image = any(
                block.block_label
                in {
                    "table",
                    "image",
                    "chart",
                    "formula",
                    "form_field",
                    "answer_line",
                    "bounded_box",
                    "checkbox",
                    "writable_area",
                }
                for block in page_blocks
            ) or bool(getattr(semantic_classifier, "requires_page_image", False))
            result = semantic_classifier.classify_page(
                page_model,
                page_blocks,
                page_context=_page_context(pages_blocks, page_index),
                page_image=_render_page_png(document[page_index]) if use_image else None,
            )
            page_model.page_role = result.page_role
            page_model.role_confidence = result.confidence
            page_model.needs_review = result.confidence < config.TASK_AUTO_APPROVE_CONFIDENCE
            native_source_blocks = [
                block for block in page_blocks if block.source == SourceKind.native_pdf
            ]
            if (
                page_index in source_nonstudent_write_pages
                or page_has_nonstudent_write_cue(native_source_blocks)
            ):
                # Page role is semantic guidance, not authority to overwrite
                # source material. A deterministic source instruction that
                # identifies a guide, key, or no-write page always wins.
                page_model.needs_review = True
                if "nonstudent_write_cue_targets_side_panel_only" not in page_model.warnings:
                    page_model.warnings.append("nonstudent_write_cue_targets_side_panel_only")
                    warnings.append(
                        f"page_{page_index}:nonstudent_write_cue_targets_side_panel_only"
                    )
            roles = {decision.block_id: decision.role for decision in result.blocks}
            for block in page_blocks:
                # Deterministic native geometry owns response-area evidence.
                # Semantic output can label text and select source IDs, but it
                # cannot demote or promote a physical write authority.
                if (
                    block.source == SourceKind.pdf_geometry
                    and block.block_label in _SAFE_RESPONSE_LABELS
                    and block.semantic_role == BlockSemanticRole.response_area
                ):
                    continue
                block.semantic_role = roles.get(block.id, block.semantic_role)
            if result.warnings:
                page_model.warnings.extend(result.warnings)
                warnings.extend(f"page_{page_index}:{warning}" for warning in result.warnings)
            semantic_results.append(result)

        all_blocks = [block for page_blocks in pages_blocks for block in page_blocks]
        try:
            tasks, response_regions = _build_tasks(
                all_blocks,
                semantic_results,
                review_mode=review_mode,
            )
        except ValueError:
            # A model may only select supplied evidence, but a contradictory
            # grouping must still fail closed instead of making the whole
            # upload error or assigning one physical destination twice.
            tasks, response_regions = [], []
            for page in pages:
                page.needs_review = True
            warnings.append("semantic_task_materialization_rejected")
        unreliable_write_pages = {
            page.page_index
            for page in pages
            if not page_has_reliable_native_write_evidence(page)
        }
        if unreliable_write_pages:
            unreliable_region_ids = {
                region.id
                for region in response_regions
                if region.page_index in unreliable_write_pages
            }
            for region in response_regions:
                if region.id in unreliable_region_ids and region.safety == ResponseSafety.approved:
                    region.safety = ResponseSafety.needs_review
            for task in tasks:
                if (
                    task.anchor_page_index in unreliable_write_pages
                    or any(
                        link.response_region_id in unreliable_region_ids
                        for link in task.response_links
                    )
                ):
                    task.side_panel_fallback = True
                    task.review_status = ReviewStatus.needs_review
            warnings.extend(
                f"page_{page_index}:unreliable_native_text_targets_side_panel_only"
                for page_index in sorted(unreliable_write_pages)
            )
        transformed_page_indexes = {
            page.page_index for page in pages if page.display_transform_required
        }
        if transformed_page_indexes:
            transformed_region_ids = {
                region.id
                for region in response_regions
                if region.page_index in transformed_page_indexes
            }
            for region in response_regions:
                if region.id in transformed_region_ids:
                    region.safety = ResponseSafety.unsafe
            for task in tasks:
                if any(
                    link.response_region_id in transformed_region_ids
                    for link in task.response_links
                ):
                    task.side_panel_fallback = True
                    task.review_status = ReviewStatus.needs_review
            for page in pages:
                if page.page_index in transformed_page_indexes:
                    page.needs_review = True
                    warnings.append(
                        f"page_{page.page_index}:transformed_physical_targets_side_panel_only"
                    )
        if any(page.extraction_status == ParseStatus.requires_ocr for page in pages):
            status = ParseStatus.requires_ocr
        elif any(page.extraction_status == ParseStatus.failed for page in pages):
            status = ParseStatus.failed
        elif any(page.needs_review for page in pages) or any(
            task.review_status == ReviewStatus.needs_review for task in tasks
        ):
            status = ParseStatus.low_confidence
        else:
            status = ParseStatus.parsed
        title_block = next(
            (
                block
                for block in all_blocks
                if block.block_label in {"doc_title", "paragraph_title", "native_text"}
                and block.text.strip()
                and any(character.isalpha() for character in block.text)
            ),
            None,
        )
        title = (title_block.text.strip() if title_block else "Untitled assignment")[:120]
        parser_name = getattr(semantic_classifier, "parser_name", "hybrid-physical-ir")
        return IntermediateDocument(
            title=title,
            parser=parser_name,
            status=status,
            source_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            pages=pages,
            blocks=all_blocks,
            response_regions=response_regions,
            tasks=tasks,
            warnings=list(dict.fromkeys(warnings)),
            processing_ms=(time.perf_counter() - started) * 1000,
        )
    finally:
        document.close()


def document_questions(document: IntermediateDocument, *, approved_only: bool = False) -> list[dict]:
    return document.task_views(include_unapproved=not approved_only, student_safe=True)
