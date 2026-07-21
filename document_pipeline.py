"""Hybrid native-PDF, PaddleOCR, and semantic document-understanding pipeline."""
from __future__ import annotations

import re
import time
from typing import Iterable

import fitz

import config
from document_model import (
    AnswerRegionStatus,
    BlockSemanticRole,
    DocumentBlock,
    DocumentPage,
    DocumentTask,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ReviewStatus,
    SourceKind,
    stable_task_id,
)
from ocr_adapter import OCRAdapter, NullOCRAdapter, get_ocr_adapter
from semantic_classifier import NullSemanticClassifier, SemanticClassifier

_NATIVE_TEXT_MIN_CHARS = 12
_SAFE_RESPONSE_LABELS = {"answer_line", "form_field"}


def _union_bbox(blocks: Iterable[DocumentBlock]) -> list[float] | None:
    items = list(blocks)
    if not items:
        return None
    return [
        min(item.bbox[0] for item in items),
        min(item.bbox[1] for item in items),
        max(item.bbox[2] for item in items),
        max(item.bbox[3] for item in items),
    ]


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
            x0, x1 = sorted((float(p0.x), float(p1.x)))
            y = float((p0.y + p1.y) / 2)
            signature = (round(x0), round(x1), round(y))
            if signature in seen:
                continue
            seen.add(signature)
            intersections = sum(
                x0 - 2 <= x <= x1 + 2 and vertical_y0 - 2 <= y <= vertical_y1 + 2
                for x, vertical_y0, vertical_y1 in verticals
            )
            nearby_blocks = [
                block
                for block in native_blocks
                if block.bbox[1] <= y
                and y - block.bbox[3] <= 50
                and block.bbox[2] >= x0 - 12
                and block.bbox[0] <= x1 + 12
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
                and x0 >= block.bbox[2] - 15
                and abs(y - block.bbox[3]) <= 16
                for block in nearby_blocks
            )
            safe_line = (
                intersections < 2
                and (explicit_prompt_evidence or explicit_field_label)
                and float(drawing.get("width") or 1) <= 1.5
            )
            blocks.append(
                DocumentBlock(
                    id=f"page-{page_index}-line-{order}",
                    page_index=page_index,
                    reading_order=order,
                    text="",
                    block_label="answer_line" if safe_line else "horizontal_rule_candidate",
                    bbox=[x0, max(0.0, y - 5), x1, min(float(page.rect.height), y + 19)],
                    confidence=0.92 if safe_line else 0.55,
                    source=SourceKind.pdf_geometry,
                    semantic_role=(
                        BlockSemanticRole.response_area if safe_line else BlockSemanticRole.unknown
                    ),
                )
            )
            order += 1
    return blocks


def _paddle_blocks(result, start_order: int = 0) -> list[DocumentBlock]:
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
                bbox=list(item.bbox),
                polygon=[list(point) for point in item.polygon] if item.polygon else None,
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
    pages: list[DocumentPage],
    blocks: list[DocumentBlock],
    semantic_results,
    *,
    review_mode: str,
) -> list[DocumentTask]:
    block_by_id = {block.id: block for block in blocks}
    tasks: list[DocumentTask] = []
    for result in semantic_results:
        if result.page_role not in {PageRole.student_worksheet, PageRole.mixed}:
            continue
        for candidate in result.tasks:
            prompt_blocks = [block_by_id[block_id] for block_id in candidate.prompt_block_ids]
            response_blocks = [block_by_id[block_id] for block_id in candidate.response_block_ids]
            safe_response_blocks = [
                block
                for block in response_blocks
                if block.block_label in _SAFE_RESPONSE_LABELS and block.confidence >= 0.85
            ]
            answer_bbox = _union_bbox(safe_response_blocks)
            if answer_bbox is not None:
                answer_status = AnswerRegionStatus.detected
            elif response_blocks:
                answer_status = AnswerRegionStatus.low_confidence
            else:
                answer_status = AnswerRegionStatus.side_panel
            confidence = min(candidate.confidence, result.confidence)
            can_auto_approve = (
                config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE
                and review_mode == "direct"
                and result.page_role == PageRole.student_worksheet
                and confidence >= config.TASK_AUTO_APPROVE_CONFIDENCE
                and answer_bbox is not None
                and all(
                    block.confidence >= config.ANSWER_REGION_AUTO_APPROVE_CONFIDENCE
                    for block in safe_response_blocks
                )
            )
            review_status = ReviewStatus.auto_approved if can_auto_approve else ReviewStatus.needs_review
            source_blocks = list(dict.fromkeys(candidate.prompt_block_ids + candidate.response_block_ids))
            task_id = stable_task_id(
                result.page_index,
                candidate.label,
                source_blocks,
                candidate.prompt_text,
            )
            tasks.append(
                DocumentTask(
                    id=task_id,
                    legacy_question_id=len(tasks) + 1,
                    label=candidate.label,
                    prompt_text=candidate.prompt_text.strip(),
                    page_index=result.page_index,
                    page_role=result.page_role,
                    prompt_bbox=_union_bbox(prompt_blocks),
                    answer_bbox=answer_bbox,
                    response_type=candidate.response_type,
                    confidence=confidence,
                    review_status=review_status,
                    answer_region_status=answer_status,
                    source_blocks=source_blocks,
                )
            )
    return tasks


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
                paddle = _paddle_blocks(result, start_order=len(page_blocks))
                paddle_block_count = len(paddle)
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
            page_model = DocumentPage(
                page_index=page_index,
                width_points=float(page.rect.width),
                height_points=float(page.rect.height),
                rotation=int(page.rotation) % 360,
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
        tasks = _build_tasks(
            pages,
            all_blocks,
            semantic_results,
            review_mode=review_mode,
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
            pages=pages,
            blocks=all_blocks,
            tasks=tasks,
            warnings=list(dict.fromkeys(warnings)),
            processing_ms=(time.perf_counter() - started) * 1000,
        )
    finally:
        document.close()


def normalized_region(bbox: list[float] | None, page: DocumentPage) -> dict[str, float] | None:
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return {
        "x": round(x0 / page.width_points, 6),
        "y": round(y0 / page.height_points, 6),
        "width": round((x1 - x0) / page.width_points, 6),
        "height": round((y1 - y0) / page.height_points, 6),
    }


def document_questions(document: IntermediateDocument, *, approved_only: bool = False) -> list[dict]:
    pages = {page.page_index: page for page in document.pages}
    questions = []
    for task in document.tasks:
        if approved_only and not task.approved:
            continue
        page = pages[task.page_index]
        questions.append(
            {
                "id": task.legacy_question_id,
                "task_id": task.id,
                "label": task.label,
                "text": task.prompt_text,
                "page": task.page_index + 1,
                "page_index": task.page_index,
                "page_role": task.page_role.value,
                "prompt_region": normalized_region(task.prompt_bbox, page),
                "answer_region": normalized_region(task.answer_bbox, page),
                "detected_answer_region": normalized_region(task.answer_bbox, page),
                "prompt_bbox": task.prompt_bbox,
                "answer_bbox": task.answer_bbox,
                "response_type": task.response_type,
                "confidence": task.confidence,
                "layout_confidence": task.confidence if task.answer_bbox else 0.0,
                "needs_layout_review": task.review_status == ReviewStatus.needs_review,
                "review_status": task.review_status.value,
                "answer_region_status": task.answer_region_status.value,
                "source_blocks": task.source_blocks,
                "approved": task.approved,
            }
        )
    return questions
