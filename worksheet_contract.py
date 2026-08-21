"""Fail-closed product contract for sequential short-answer worksheets."""

from __future__ import annotations

from collections import defaultdict

import config
from document_model import (
    BlockSemanticRole,
    CoordinateSpace,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ResponseRegionType,
    ResponseSafety,
    ResponseType,
    ReviewStatus,
    SourceKind,
    TaskResponseRole,
    WorksheetClassification,
    WorksheetSupportStatus,
)

_SUPPORTED_RESPONSE_TYPES = {ResponseType.short_text, ResponseType.numeric}
_SUPPORTED_REGION_TYPES = {
    ResponseRegionType.answer_line,
    ResponseRegionType.bounded_box,
    ResponseRegionType.form_field,
    ResponseRegionType.writable_area,
}
_SUPPORTED_PHYSICAL_LABELS = {item.value for item in _SUPPORTED_REGION_TYPES}
_MAX_LOCAL_RESPONSE_GAP_POINTS = 120.0
_MAX_SHORT_ANSWER_HEIGHT_POINTS = 180.0


class UnsupportedWorksheetError(ValueError):
    """Controlled rejection for an unsupported or ambiguous worksheet."""

    def __init__(self, classification: WorksheetClassification):
        self.classification = classification
        if "semantic_call_budget_exceeded" in classification.reason_codes:
            message = (
                "This worksheet exceeds Claros's processing limit. "
                "Use a worksheet with no more than eight pages and forty questions."
            )
        elif classification.status == WorksheetSupportStatus.ambiguous:
            message = (
                "Claros could not safely match every question to one local blank answer space. "
                "This worksheet format is unsupported."
            )
        else:
            message = (
                "This worksheet format is unsupported. Claros supports sequential short-answer "
                "questions with a blank line or box directly beneath each question."
            )
        super().__init__(message)
        self.user_message = message


def workload_rejection(
    reason_code: str,
    *,
    question_count: int = 0,
    semantic_provider_calls: int = 0,
) -> UnsupportedWorksheetError:
    return UnsupportedWorksheetError(
        WorksheetClassification(
            status=WorksheetSupportStatus.unsupported,
            reason_codes=[reason_code],
            question_count=question_count,
            semantic_provider_calls=semantic_provider_calls,
        )
    )


def _bbox_union(blocks) -> list[float] | None:
    boxes = [block.bbox for block in blocks if block.bbox is not None]
    if len(boxes) != len(blocks) or not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _horizontal_overlap(first: list[float], second: list[float]) -> float:
    return max(0.0, min(first[2], second[2]) - max(first[0], second[0]))


def _aligned_answer_line_group(regions) -> bool:
    """Recognize multiple lines as one local response space, not many targets."""
    if len(regions) <= 1:
        return True
    if any(region.region_type != ResponseRegionType.answer_line for region in regions):
        return False
    ordered = sorted(regions, key=lambda region: (region.bbox[1], region.bbox[0], region.id))
    for previous, current in zip(ordered, ordered[1:]):
        narrower_width = min(
            previous.bbox[2] - previous.bbox[0],
            current.bbox[2] - current.bbox[0],
        )
        if (
            current.bbox[1] < previous.bbox[3]
            or current.bbox[1] - previous.bbox[3] > 48
            or narrower_width <= 0
            or _horizontal_overlap(previous.bbox, current.bbox) < narrower_width * 0.8
        ):
            return False
    return True


def classify_supported_worksheet(document: IntermediateDocument) -> WorksheetClassification:
    """Classify the whole canonical document against the active product contract."""
    unsupported: set[str] = set()
    ambiguous: set[str] = set()
    question_count = len(document.tasks)

    if not document.tasks:
        unsupported.add("no_questions")
    if question_count > config.MAX_WORKSHEET_QUESTIONS:
        unsupported.add("question_limit_exceeded")
    if document.semantic_provider_calls > config.MAX_SEMANTIC_PROVIDER_CALLS:
        unsupported.add("semantic_call_budget_exceeded")
    if document.status in {ParseStatus.requires_ocr, ParseStatus.failed}:
        unsupported.add("unreliable_document_extraction")

    block_by_id = {block.id: block for block in document.blocks}
    region_by_id = {region.id: region for region in document.response_regions}
    tasks_by_page: dict[int, list] = defaultdict(list)
    linked_source_ids: set[str] = set()

    if any(block.block_label == "table" for block in document.blocks):
        unsupported.add("table_layout")

    for page in document.pages:
        if page.coordinate_space != CoordinateSpace.pdf_points or page.rotation != 0 or page.display_transform_required:
            unsupported.add("transformed_page")
        if page.page_role in {PageRole.answer_key, PageRole.teacher_guide, PageRole.reference_material}:
            unsupported.add("nonstudent_page")
        elif page.page_role != PageRole.student_worksheet:
            ambiguous.add("uncertain_page_role")
        if page.extraction_status != ParseStatus.parsed or page.ocr_required or not page.native_text_exists:
            unsupported.add("unreliable_page_extraction")
        if page.needs_review:
            ambiguous.add("page_requires_review")

    for task in sorted(document.tasks, key=lambda item: item.order):
        tasks_by_page[task.anchor_page_index].append(task)
        if task.response_type not in _SUPPORTED_RESPONSE_TYPES:
            unsupported.add("unsupported_response_type")
        if task.choices:
            unsupported.add("choice_task")
        if task.page_role != PageRole.student_worksheet:
            ambiguous.add("uncertain_task_role")
        if task.review_status not in {ReviewStatus.auto_approved, ReviewStatus.approved}:
            ambiguous.add("task_requires_review")
        if task.side_panel_fallback:
            ambiguous.add("side_panel_parse_fallback")

        prompt_blocks = [block_by_id.get(block_id) for block_id in task.prompt_block_ids]
        if (
            not prompt_blocks
            or any(block is None for block in prompt_blocks)
            or any(
                block.source != SourceKind.native_pdf
                or block.page_index != task.anchor_page_index
                or block.bbox is None
                for block in prompt_blocks
                if block is not None
            )
        ):
            ambiguous.add("unreliable_question_geometry")
            continue
        prompt_box = _bbox_union(prompt_blocks)
        if prompt_box is None:
            ambiguous.add("unreliable_question_geometry")
            continue

        if not task.response_links:
            ambiguous.add("missing_answer_region")
            continue
        regions = []
        for link in sorted(task.response_links, key=lambda item: item.order):
            if link.role != TaskResponseRole.answer:
                unsupported.add("multiple_response_roles")
            region = region_by_id.get(link.response_region_id)
            if region is None:
                ambiguous.add("missing_answer_region")
                continue
            regions.append(region)
            linked_source_ids.update(region.source_block_ids)
            if region.page_index != task.anchor_page_index:
                ambiguous.add("cross_page_answer_region")
            if region.region_type not in _SUPPORTED_REGION_TYPES:
                unsupported.add("unsupported_answer_geometry")
            if region.response_type not in _SUPPORTED_RESPONSE_TYPES:
                unsupported.add("unsupported_response_type")
            if region.safety != ResponseSafety.approved:
                ambiguous.add("unapproved_answer_region")
            if region.bbox[1] < prompt_box[3] - 2:
                ambiguous.add("answer_not_below_question")
            elif region.bbox[1] - prompt_box[3] > _MAX_LOCAL_RESPONSE_GAP_POINTS:
                ambiguous.add("remote_answer_region")
        if not _aligned_answer_line_group(regions):
            ambiguous.add("ambiguous_answer_region_group")
        response_box = _bbox_union(regions)
        if response_box is not None and response_box[3] - response_box[1] > _MAX_SHORT_ANSWER_HEIGHT_POINTS:
            unsupported.add("long_form_answer_area")

    for page_index, tasks in tasks_by_page.items():
        ordered = sorted(tasks, key=lambda task: task.order)
        prompt_boxes: list[tuple[object, list[float]]] = []
        for task in ordered:
            blocks = [block_by_id.get(block_id) for block_id in task.prompt_block_ids]
            if not blocks or any(block is None for block in blocks):
                continue
            box = _bbox_union(blocks)
            if box is not None:
                prompt_boxes.append((task, box))
        for index, (task, prompt_box) in enumerate(prompt_boxes):
            next_prompt_top = (
                prompt_boxes[index + 1][1][1]
                if index + 1 < len(prompt_boxes)
                else document.page(page_index).height_points
            )
            if index and prompt_box[1] <= prompt_boxes[index - 1][1][1] + 2:
                unsupported.add("non_linear_question_order")
            if index:
                previous_box = prompt_boxes[index - 1][1]
                if prompt_box[1] < previous_box[3] - 2:
                    unsupported.add("multi_column_layout")
                elif (
                    abs(prompt_box[0] - previous_box[0]) > 96
                    and _horizontal_overlap(previous_box, prompt_box) == 0
                ):
                    unsupported.add("multi_column_layout")
            for link in task.response_links:
                region = region_by_id.get(link.response_region_id)
                if region is not None and region.page_index == page_index and region.bbox[3] > next_prompt_top + 2:
                    ambiguous.add("answer_crosses_next_question")

    pages_with_questions = set(tasks_by_page)
    if pages_with_questions != {page.page_index for page in document.pages}:
        unsupported.add("page_without_question")

    physical_response_ids = {
        block.id
        for block in document.blocks
        if block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label in _SUPPORTED_PHYSICAL_LABELS
        and block.bbox is not None
    }
    if physical_response_ids - linked_source_ids:
        ambiguous.add("unclaimed_writable_space")

    if unsupported:
        status = WorksheetSupportStatus.unsupported
        reasons = sorted(unsupported | ambiguous)
    elif ambiguous:
        status = WorksheetSupportStatus.ambiguous
        reasons = sorted(ambiguous)
    else:
        status = WorksheetSupportStatus.supported
        reasons = []
    return WorksheetClassification(
        status=status,
        reason_codes=reasons,
        question_count=question_count,
        semantic_provider_calls=document.semantic_provider_calls,
    )
