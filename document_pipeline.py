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
    TaskResponseLink,
    source_prompt_text,
    stable_response_region_id,
    stable_task_id,
)
from ocr_adapter import OCRAdapter, NullOCRAdapter, get_ocr_adapter
from semantic_classifier import NullSemanticClassifier, SemanticClassifier

_NATIVE_TEXT_MIN_CHARS = 12
_SAFE_RESPONSE_LABELS = {"answer_line", "form_field"}


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


def _native_blocks(page: fitz.Page, page_index: int) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    order = 0
    raw = page.get_text("dict", sort=True)
    for raw_block in raw.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        for line in raw_block.get("lines", []):
            text = " ".join(
                str(span.get("text") or "").strip()
                for span in line.get("spans", [])
                if str(span.get("text") or "").strip()
            ).strip()
            if not text:
                continue
            raw_bbox = line.get("bbox") or raw_block.get("bbox")
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


def _physical_response_blocks(
    page: fitz.Page,
    page_index: int,
    start_order: int,
    native_blocks: list[DocumentBlock],
) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    order = start_order
    page_width, page_height = _page_extraction_dimensions(page)
    widgets = page.widgets()
    if widgets is not None:
        for widget in widgets:
            rect = widget.rect
            if rect.width < 24 or rect.height < 18:
                continue
            blocks.append(
                DocumentBlock(
                    id=f"page-{page_index}-field-{order}",
                    page_index=page_index,
                    reading_order=order,
                    text="",
                    block_label="form_field",
                    bbox=[rect.x0, rect.y0, rect.x1, rect.y1],
                    confidence=1.0,
                    source=SourceKind.pdf_geometry,
                    semantic_role=BlockSemanticRole.response_area,
                )
            )
            order += 1

    for native in native_blocks:
        if "_" not in native.text:
            continue
        blank_at = native.text.find("_")
        x0 = native.bbox[0] + (native.bbox[2] - native.bbox[0]) * blank_at / max(1, len(native.text))
        blocks.append(
            DocumentBlock(
                id=f"page-{page_index}-underscore-{order}",
                page_index=page_index,
                reading_order=order,
                text="",
                block_label="answer_line",
                bbox=[max(native.bbox[0], x0 - 4), native.bbox[1] - 3, native.bbox[2], native.bbox[3] + 15],
                confidence=0.97,
                source=SourceKind.pdf_geometry,
                semantic_role=BlockSemanticRole.response_area,
            )
        )
        order += 1

    # Vector rules are physical evidence, but table grids and decorative rules
    # are only candidates. A writable answer line needs nearby prompt/answer text
    # and must not be crossed by multiple vertical grid lines.
    seen: set[tuple[int, int, int]] = set()
    drawings = page.get_drawings()
    verticals: list[tuple[float, float, float]] = []
    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item or item[0] != "l":
                continue
            p0, p1 = item[1], item[2]
            if abs(p0.x - p1.x) <= 2 and abs(p1.y - p0.y) >= 18:
                verticals.append((float((p0.x + p1.x) / 2), min(p0.y, p1.y), max(p0.y, p1.y)))
    for drawing in drawings:
        for item in drawing.get("items", []):
            if not item or item[0] != "l":
                continue
            p0, p1 = item[1], item[2]
            if abs(p0.y - p1.y) > 2 or abs(p1.x - p0.x) < 80:
                continue
            raw_x0, raw_x1 = sorted((float(p0.x), float(p1.x)))
            y = float((p0.y + p1.y) / 2)
            signature = (round(raw_x0), round(raw_x1), round(y))
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
                if block.bbox[1] <= y
                and y - block.bbox[3] <= 50
                and block.bbox[2] >= raw_x0 - 12
                and block.bbox[0] <= raw_x1 + 12
            ]
            nearby_text = " ".join(block.text for block in nearby_blocks)
            explicit_prompt_evidence = bool(
                re.search(
                    r"\?|\b(answer|response|explain|describe|calculate|solve|write|record|why|what|how)\b",
                    nearby_text,
                    re.IGNORECASE,
                )
            )
            explicit_field_label = any(
                block.text.rstrip().endswith(":")
                and raw_x0 >= block.bbox[2] - 15
                and abs(y - block.bbox[3]) <= 16
                for block in nearby_blocks
            )
            safe_line = (
                intersections < 2
                and (explicit_prompt_evidence or explicit_field_label)
                and float(drawing.get("width") or 1) <= 1.5
            )
            bbox = _clip_bbox_to_page(
                [raw_x0, max(0.0, y - 5), raw_x1, min(page_height, y + 19)],
                page_width,
                page_height,
            )
            if bbox is None:
                continue
            geometry_clipped = bbox != [raw_x0, max(0.0, y - 5), raw_x1, min(page_height, y + 19)]
            blocks.append(
                DocumentBlock(
                    id=f"page-{page_index}-line-{order}",
                    page_index=page_index,
                    reading_order=order,
                    text="",
                    block_label=(
                        "clipped_response_candidate"
                        if geometry_clipped
                        else "answer_line"
                        if safe_line
                        else "horizontal_rule_candidate"
                    ),
                    bbox=bbox,
                    confidence=0.92 if safe_line else 0.55,
                    source=SourceKind.pdf_geometry,
                    semantic_role=(
                        BlockSemanticRole.response_area
                        if safe_line and not geometry_clipped
                        else BlockSemanticRole.unknown
                    ),
                )
            )
            order += 1
    return blocks


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
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if not item:
                continue
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


def _build_tasks(
    blocks: list[DocumentBlock],
    semantic_results,
    *,
    review_mode: str,
) -> tuple[list[DocumentTask], list[DocumentResponseRegion]]:
    """Materialize semantic selections without merging physical response areas."""
    block_by_id = {block.id: block for block in blocks}

    def physical_order(block: DocumentBlock) -> tuple[int, int, float, float, str]:
        bbox = block.bbox or [float("inf"), float("inf"), float("inf"), float("inf")]
        return (block.page_index, block.reading_order, bbox[1], bbox[0], block.id)

    def ordered_blocks(block_ids: list[str], label: str) -> list[DocumentBlock]:
        if len(block_ids) != len(set(block_ids)):
            raise ValueError(f"semantic task has duplicate {label} block IDs")
        return sorted((block_by_id[block_id] for block_id in block_ids), key=physical_order)

    tasks: list[DocumentTask] = []
    response_regions: list[DocumentResponseRegion] = []
    claimed_response_block_ids: set[str] = set()
    claimed_response_blocks: list[DocumentBlock] = []
    task_ids: set[str] = set()

    def candidate_sort_key(item) -> tuple[int, int, float, float, str, str]:
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
        prompt_blocks = ordered_blocks(candidate.prompt_block_ids, "prompt")
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
        eligible_response_blocks = [
            block
            for block in response_blocks
            if block.bbox is not None
            and block.block_label in _SAFE_RESPONSE_LABELS
            and block.confidence >= 0.85
        ]
        confidence = min(candidate.confidence, result.confidence)
        can_auto_approve = (
            config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE
            and review_mode == "direct"
            and result.page_role == PageRole.student_worksheet
            and confidence >= config.TASK_AUTO_APPROVE_CONFIDENCE
            and bool(eligible_response_blocks)
            and len(eligible_response_blocks) == len(response_blocks)
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
        for response_order, block in enumerate(response_blocks):
            if block.bbox is None:
                continue
            region_type = {
                "answer_line": ResponseRegionType.answer_line,
                "form_field": ResponseRegionType.form_field,
                "checkbox": ResponseRegionType.checkbox,
                "bounded_box": ResponseRegionType.bounded_box,
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
            response_regions.append(
                DocumentResponseRegion(
                    id=region_id,
                    page_index=block.page_index,
                    bbox=block.bbox,
                    region_type=region_type,
                    response_type=candidate.response_type,
                    safety=safety,
                    confidence=min(confidence, block.confidence),
                    source_block_ids=[block.id],
                )
            )
            response_links.append(
                TaskResponseLink(
                    response_region_id=region_id,
                    order=response_order,
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
                response_links=response_links,
                side_panel_fallback=not response_links
                or any(
                    region.safety != ResponseSafety.approved
                    for region in response_regions[-len(response_links) :]
                ),
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
        warnings: list[str] = []

        for page_index, page in enumerate(document):
            display_transform_required = _page_requires_display_transform(page)
            page_width, page_height = _page_extraction_dimensions(page)
            native = _native_blocks(page, page_index)
            native_char_count = sum(len(block.text.strip()) for block in native)
            native_reliable = native_char_count >= _NATIVE_TEXT_MIN_CHARS
            page_blocks = list(native)
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

            physical = _physical_response_blocks(page, page_index, len(page_blocks), native)
            page_blocks.extend(physical)
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
                block.block_label in {"table", "image", "chart", "formula", "form_field", "answer_line"}
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
            roles = {decision.block_id: decision.role for decision in result.blocks}
            for block in page_blocks:
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
