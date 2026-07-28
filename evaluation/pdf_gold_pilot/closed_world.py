"""Closed-world Gemini task grouping for the isolated PDF gold pilot."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, model_validator

from config import get_api_key, get_text_model
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
    ResponseType,
    ReviewStatus,
    SourceKind,
    TaskResponseLink,
)

logger = logging.getLogger(__name__)


class PilotPhysicalBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=0)
    reading_order: int = Field(ge=0)
    text: str = ""
    block_label: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    polygon: list[list[float]] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    semantic_role: str = "unknown"


class PilotResponseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=0)
    reading_order: int = Field(ge=0)
    layout_label: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    safe_for_writing: bool
    safety_suggestion: Literal["safe_physical", "ambiguous"]


class PilotPageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_id: str
    source_pdf: str
    page_number: int = Field(ge=1)
    page_index: int = Field(ge=0)
    page_width_points: float = Field(gt=0)
    page_height_points: float = Field(gt=0)
    rotation: Literal[0, 90, 180, 270]
    display_transform_required: bool = False
    image: str
    blocks: list[PilotPhysicalBlock]
    response_candidates: list[PilotResponseCandidate]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ids(self):
        block_ids = [block.id for block in self.blocks]
        response_ids = [candidate.id for candidate in self.response_candidates]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("physical block IDs must be unique")
        if len(response_ids) != len(set(response_ids)):
            raise ValueError("response candidate IDs must be unique")
        if set(block_ids) & set(response_ids):
            raise ValueError("physical block and response candidate IDs must be disjoint")
        if any(block.page_index != self.page_index for block in self.blocks):
            raise ValueError("all blocks must belong to the input page")
        if any(candidate.page_index != self.page_index for candidate in self.response_candidates):
            raise ValueError("all response candidates must belong to the input page")
        for block in self.blocks:
            x0, y0, x1, y1 = block.bbox
            if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0 or x1 > self.page_width_points or y1 > self.page_height_points:
                raise ValueError("physical block geometry must stay within the extraction frame")
        for candidate in self.response_candidates:
            x0, y0, x1, y1 = candidate.bbox
            if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0 or x1 > self.page_width_points or y1 > self.page_height_points:
                raise ValueError("response candidate geometry must stay within the extraction frame")
        return self


RejectionReason = Literal[
    "teacher_instruction",
    "answer_key_content",
    "example",
    "rubric",
    "standard",
    "reference_value",
    "navigation",
    "decorative",
    "not_student_answerable",
    "uncertain",
]
ResponseDisposition = Literal["safe_physical", "ambiguous", "unsafe", "side_panel_only"]


class ClosedWorldRejectedBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    reason: RejectionReason


class ClosedWorldTaskGrouping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_index: int = Field(ge=1)
    prompt_block_ids: list[str] = Field(min_length=1)
    visual_anchor_block_ids: list[str] = Field(default_factory=list)
    parent_group_index: int | None = Field(default=None, ge=1)
    subpart: str | None = None
    response_candidate_ids: list[str] = Field(default_factory=list)
    response_disposition: ResponseDisposition
    needs_review: bool
    reason: str


class ClosedWorldPageResult(BaseModel):
    """The complete set of values Gemini may return in this experiment."""

    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0)
    page_role: PageRole
    selected_block_ids: list[str]
    rejected_blocks: list[ClosedWorldRejectedBlock]
    groupings: list[ClosedWorldTaskGrouping]
    selected_response_candidate_ids: list[str]
    needs_review: bool
    reason: str

    @model_validator(mode="after")
    def validate_unique_output(self):
        rejected_ids = [item.block_id for item in self.rejected_blocks]
        group_indexes = [item.group_index for item in self.groupings]
        if len(self.selected_block_ids) != len(set(self.selected_block_ids)):
            raise ValueError("selected block IDs must be unique")
        if len(rejected_ids) != len(set(rejected_ids)):
            raise ValueError("rejected block IDs must be unique")
        if len(group_indexes) != len(set(group_indexes)):
            raise ValueError("group indexes must be unique")
        if len(self.selected_response_candidate_ids) != len(set(self.selected_response_candidate_ids)):
            raise ValueError("selected response candidate IDs must be unique")
        return self


_SYSTEM_INSTRUCTION = """You are the closed-world semantic classifier in an offline Claros evaluation.
Claros helps students with typing difficulties answer educational PDFs. Select and group only the supplied
physical blocks. Never invent a block ID, response candidate ID, coordinate, prompt text, or answer area.
Use the page image, layout labels, coordinates, and reading order. A numbered line is not automatically a task.
Reject teacher directions, answer-key content, examples, rubrics, standards, reference values, navigation,
decorative content, and non-answerable procedure steps. Group continuation blocks and parent/subparts correctly.
Only select a supplied response candidate. When none is reliable, choose side_panel_only or needs_review.
The result is an evaluation proposal and never authorizes writing to the PDF."""


def _prompt(page: PilotPageInput) -> str:
    return json.dumps(
        {
            "page_index": page.page_index,
            "page_width_points": page.page_width_points,
            "page_height_points": page.page_height_points,
            "rotation": page.rotation,
            "display_transform_required": page.display_transform_required,
            "blocks": [
                {
                    "id": block.id,
                    "reading_order": block.reading_order,
                    "layout_label": block.block_label,
                    "bbox_points": block.bbox,
                    "confidence": block.confidence,
                    "text": block.text,
                }
                for block in page.blocks
            ],
            "response_region_candidates": [candidate.model_dump(mode="json") for candidate in page.response_candidates],
        },
        ensure_ascii=False,
    )


def validate_closed_world_result(page: PilotPageInput, result: ClosedWorldPageResult) -> None:
    if result.page_index != page.page_index:
        raise ValueError("closed-world page_index did not match the requested page")
    known_blocks = {block.id for block in page.blocks}
    selected = set(result.selected_block_ids)
    rejected = {item.block_id for item in result.rejected_blocks}
    if selected & rejected:
        raise ValueError("a block cannot be both selected and rejected")
    if selected | rejected != known_blocks:
        raise ValueError("selected and rejected IDs must exactly partition physical blocks")

    known_groups = {group.group_index for group in result.groupings}
    grouped_selected: set[str] = set()
    prompt_memberships: list[str] = []
    selected_responses: set[str] = set()
    response_memberships: list[str] = []
    response_by_id = {candidate.id: candidate for candidate in page.response_candidates}
    for group in result.groupings:
        referenced = set(group.prompt_block_ids + group.visual_anchor_block_ids)
        if not referenced <= selected:
            raise ValueError("task grouping referenced a non-selected block")
        grouped_selected.update(referenced)
        prompt_memberships.extend(group.prompt_block_ids)
        if group.parent_group_index is not None:
            if group.parent_group_index not in known_groups or group.parent_group_index == group.group_index:
                raise ValueError("parent group reference was invalid")
        candidate_ids = set(group.response_candidate_ids)
        if not candidate_ids <= set(response_by_id):
            raise ValueError("task grouping referenced an unknown response candidate")
        selected_responses.update(candidate_ids)
        response_memberships.extend(group.response_candidate_ids)
        if group.response_disposition == "side_panel_only" and candidate_ids:
            raise ValueError("side_panel_only tasks cannot select a response candidate")
        if group.response_disposition != "side_panel_only" and not candidate_ids:
            raise ValueError("physical response dispositions require a selected candidate")
        if group.response_disposition == "safe_physical" and not all(
            response_by_id[item].safe_for_writing for item in candidate_ids
        ):
            raise ValueError("safe_physical referenced an unsafe physical candidate")

    if len(prompt_memberships) != len(set(prompt_memberships)):
        raise ValueError("a prompt block cannot belong to multiple task groups")
    if grouped_selected != selected:
        raise ValueError("every selected block must appear in a task grouping")
    if selected_responses != set(result.selected_response_candidate_ids):
        raise ValueError("selected response IDs must equal grouped response IDs")
    if len(response_memberships) != len(set(response_memberships)):
        raise ValueError("a response candidate cannot belong to multiple task groups")
    if result.page_role not in {PageRole.student_worksheet, PageRole.mixed} and result.groupings:
        raise ValueError("non-student page roles cannot contain student task groupings")


def _union_bbox(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def derive_tasks(page: PilotPageInput, result: ClosedWorldPageResult) -> list[dict]:
    """Derive task text and geometry without model-authored text or coordinates."""
    validate_closed_world_result(page, result)
    block_by_id = {block.id: block for block in page.blocks}
    response_by_id = {candidate.id: candidate for candidate in page.response_candidates}
    derived = []
    for grouping in sorted(result.groupings, key=lambda item: item.group_index):
        prompt_blocks = sorted(
            (block_by_id[block_id] for block_id in grouping.prompt_block_ids),
            key=lambda block: (block.reading_order, block.bbox[1], block.bbox[0]),
        )
        response_candidates = [response_by_id[item] for item in grouping.response_candidate_ids]
        seed = "\x1f".join([str(page.page_index), *grouping.prompt_block_ids])
        task_id = f"cw-{page.page_index + 1}-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:10]}"
        derived.append(
            {
                "id": task_id,
                "page_index": page.page_index,
                "page_role": result.page_role.value,
                "group_index": grouping.group_index,
                "parent_group_index": grouping.parent_group_index,
                "subpart": grouping.subpart,
                "prompt_text": "\n".join(block.text.strip() for block in prompt_blocks if block.text.strip()),
                "prompt_block_ids": grouping.prompt_block_ids,
                "visual_anchor_block_ids": grouping.visual_anchor_block_ids,
                "prompt_bbox": _union_bbox([block.bbox for block in prompt_blocks]),
                "response_candidate_ids": grouping.response_candidate_ids,
                "response_bbox": _union_bbox([candidate.bbox for candidate in response_candidates]),
                "response_disposition": grouping.response_disposition,
                "needs_review": grouping.needs_review,
                "reason": grouping.reason,
                "write_authorized": False,
            }
        )
    return derived


def _source_kind(value: str) -> SourceKind:
    try:
        return SourceKind(value)
    except ValueError:
        return SourceKind.pdf_geometry


def _region_type(layout_label: str) -> ResponseRegionType:
    return {
        "answer_line": ResponseRegionType.answer_line,
        "form_field": ResponseRegionType.form_field,
        "checkbox": ResponseRegionType.checkbox,
        "bounded_box": ResponseRegionType.bounded_box,
    }.get(layout_label, ResponseRegionType.unknown)


_APPROVABLE_RESPONSE_LAYOUT_LABELS = {
    "answer_line",
    "bounded_box",
    "checkbox",
    "form_field",
    "writable_area",
}


def _candidate_can_be_physically_approved(
    page: PilotPageInput,
    candidate: PilotResponseCandidate,
    grouping: ClosedWorldTaskGrouping,
) -> bool:
    """Apply the production physical-write eligibility boundary to pilot data."""
    return (
        grouping.response_disposition == "safe_physical"
        and candidate.safe_for_writing
        and candidate.layout_label in _APPROVABLE_RESPONSE_LAYOUT_LABELS
        and page.rotation == 0
        and not page.display_transform_required
    )


def _derive_canonical_page_components(
    page: PilotPageInput,
    result: ClosedWorldPageResult,
) -> tuple[
    DocumentPage,
    list[DocumentBlock],
    list[DocumentResponseRegion],
    list[DocumentTask],
]:
    """Project one validated page without making it a standalone document."""
    validate_closed_world_result(page, result)
    source_blocks = [
        DocumentBlock(
            id=block.id,
            page_index=block.page_index,
            reading_order=block.reading_order,
            text=block.text,
            block_label=block.block_label,
            bbox=block.bbox,
            polygon=block.polygon,
            confidence=block.confidence,
            source=_source_kind(block.source),
            semantic_role=BlockSemanticRole.student_prompt,
        )
        for block in page.blocks
    ]
    candidate_blocks = [
        DocumentBlock(
            id=candidate.id,
            page_index=candidate.page_index,
            reading_order=candidate.reading_order,
            text="",
            block_label=candidate.layout_label,
            bbox=candidate.bbox,
            confidence=candidate.confidence,
            source=_source_kind(candidate.source),
            semantic_role=BlockSemanticRole.response_area,
        )
        for candidate in page.response_candidates
    ]
    candidate_by_id = {candidate.id: candidate for candidate in page.response_candidates}
    derived = derive_tasks(page, result)
    grouping_by_index = {group.group_index: group for group in result.groupings}
    task_id_by_group = {item["group_index"]: item["id"] for item in derived}
    regions: list[DocumentResponseRegion] = []
    tasks: list[DocumentTask] = []
    for order, item in enumerate(derived):
        grouping = grouping_by_index[item["group_index"]]
        links: list[TaskResponseLink] = []
        has_unapproved_region = False
        for link_order, candidate_id in enumerate(grouping.response_candidate_ids):
            candidate = candidate_by_id[candidate_id]
            region_id = f"cw-region-{candidate_id}"
            if _candidate_can_be_physically_approved(page, candidate, grouping):
                safety = ResponseSafety.approved
            elif grouping.response_disposition == "unsafe":
                safety = ResponseSafety.unsafe
            else:
                safety = ResponseSafety.needs_review
            has_unapproved_region = has_unapproved_region or safety != ResponseSafety.approved
            regions.append(
                DocumentResponseRegion(
                    id=region_id,
                    page_index=candidate.page_index,
                    bbox=candidate.bbox,
                    region_type=_region_type(candidate.layout_label),
                    response_type=ResponseType.checkbox
                    if candidate.layout_label == "checkbox"
                    else ResponseType.short_text,
                    safety=safety,
                    confidence=candidate.confidence,
                    source_block_ids=[candidate.id],
                )
            )
            links.append(TaskResponseLink(response_region_id=region_id, order=link_order))
        side_panel_fallback = (
            grouping.response_disposition != "safe_physical" or has_unapproved_region
        )
        review_status = (
            ReviewStatus.needs_review
            if grouping.needs_review or side_panel_fallback
            else ReviewStatus.auto_approved
        )
        tasks.append(
            DocumentTask(
                id=item["id"],
                legacy_question_id=order + 1,
                order=order,
                label=str(grouping.group_index),
                prompt_text=item["prompt_text"],
                anchor_page_index=page.page_index,
                page_role=result.page_role,
                prompt_block_ids=item["prompt_block_ids"],
                parent_task_id=(
                    task_id_by_group.get(grouping.parent_group_index)
                    if grouping.parent_group_index is not None
                    else None
                ),
                subpart=grouping.subpart,
                response_links=links,
                side_panel_fallback=side_panel_fallback,
                response_type=ResponseType.short_text,
                confidence=1.0,
                review_status=review_status,
            )
        )
    return (
        DocumentPage(
            page_index=page.page_index,
            width_points=page.page_width_points,
            height_points=page.page_height_points,
            rotation=page.rotation,
            display_transform_required=page.display_transform_required,
            page_role=result.page_role,
            needs_review=result.needs_review
            or page.rotation != 0
            or page.display_transform_required,
            block_ids=[block.id for block in source_blocks + candidate_blocks],
            warnings=(
                [*page.warnings, "transformed_physical_targets_side_panel_only"]
                if (page.rotation != 0 or page.display_transform_required)
                and "transformed_physical_targets_side_panel_only" not in page.warnings
                else list(page.warnings)
            ),
        ),
        source_blocks + candidate_blocks,
        regions,
        tasks,
    )


def derive_canonical_document_for_pages(
    pages: list[PilotPageInput],
    results: list[ClosedWorldPageResult],
) -> IntermediateDocument:
    """Assemble a production document from actual, contiguous source pages.

    Inputs may arrive in any order, but must cover page indexes ``0..N-1``
    from one source PDF. This deliberately rejects a standalone nonzero page:
    inserting blank page records would invent physical document evidence.
    """
    if not pages:
        raise ValueError("canonical document assembly requires at least one page")
    if len(pages) != len(results):
        raise ValueError("canonical document assembly requires one result per page")

    page_results = list(zip(pages, results, strict=True))
    page_indexes = [page.page_index for page, _ in page_results]
    if len(page_indexes) != len(set(page_indexes)):
        raise ValueError("canonical document page indexes must be unique")
    if set(page_indexes) != set(range(len(page_results))):
        raise ValueError("canonical document page indexes must be contiguous from zero")
    if len({page.source_pdf for page, _ in page_results}) != 1:
        raise ValueError("canonical document pages must share one source PDF")

    for page, result in page_results:
        validate_closed_world_result(page, result)

    ordered_page_results = sorted(page_results, key=lambda item: item[0].page_index)
    physical_ids = [
        item.id
        for page, _ in ordered_page_results
        for item in [*page.blocks, *page.response_candidates]
    ]
    if len(physical_ids) != len(set(physical_ids)):
        raise ValueError("canonical document physical block IDs must be globally unique")

    document_pages: list[DocumentPage] = []
    blocks: list[DocumentBlock] = []
    response_regions: list[DocumentResponseRegion] = []
    task_entries: list[tuple[int, int, DocumentTask]] = []
    for page, result in ordered_page_results:
        document_page, page_blocks, page_regions, page_tasks = _derive_canonical_page_components(
            page,
            result,
        )
        document_pages.append(document_page)
        blocks.extend(page_blocks)
        response_regions.extend(page_regions)
        task_entries.extend(
            (page.page_index, task.order, task)
            for task in page_tasks
        )

    ordered_tasks = sorted(task_entries, key=lambda item: (item[0], item[1], item[2].id))
    tasks = [
        task.model_copy(update={"order": order, "legacy_question_id": order + 1})
        for order, (_, _, task) in enumerate(ordered_tasks)
    ]
    source_pdf = ordered_page_results[0][0].source_pdf
    return IntermediateDocument(
        title=source_pdf,
        parser="closed-world-evaluation-adapter",
        status=(
            ParseStatus.low_confidence
            if any(page.needs_review for page in document_pages)
            else ParseStatus.parsed
        ),
        document_id=source_pdf,
        pages=document_pages,
        blocks=blocks,
        response_regions=response_regions,
        tasks=tasks,
        warnings=[warning for page in document_pages for warning in page.warnings],
    )


def derive_canonical_document(page: PilotPageInput, result: ClosedWorldPageResult) -> IntermediateDocument:
    """Project a page-zero evaluation proposal into the production contract.

    The compatibility entry point cannot safely assemble page one or later by
    itself. Call :func:`derive_canonical_document_for_pages` with every actual
    contiguous page instead.
    """
    if page.page_index != 0:
        raise ValueError(
            "standalone canonical document derivation requires page_index 0; "
            "use derive_canonical_document_for_pages for contiguous pages"
        )
    document = derive_canonical_document_for_pages([page], [result])
    return document.model_copy(update={"title": page.pilot_id, "document_id": page.pilot_id})


class ClosedWorldGeminiClassifier:
    """Existing Gemini integration constrained to supplied IDs and geometry."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self._model = model

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(
                api_key=get_api_key(),
                http_options=types.HttpOptions(api_version="v1alpha"),
            )
        return self._client

    def classify_page(self, page: PilotPageInput, page_image: bytes) -> ClosedWorldPageResult:
        contents: list[object] = [
            _prompt(page),
            types.Part.from_bytes(data=page_image, mime_type="image/png"),
        ]
        try:
            response = self._get_client().models.generate_content(
                model=self._model or get_text_model(),
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_json_schema=ClosedWorldPageResult.model_json_schema(),
                    temperature=0,
                ),
            )
            raw = getattr(response, "parsed", None)
            if isinstance(raw, ClosedWorldPageResult):
                result = raw
            elif raw is not None:
                result = ClosedWorldPageResult.model_validate(raw)
            else:
                result = ClosedWorldPageResult.model_validate_json(response.text or "")
            validate_closed_world_result(page, result)
            return result
        except Exception as exc:
            logger.warning(
                "Closed-world classification rejected pilot_id=%s error_type=%s",
                page.pilot_id,
                type(exc).__name__,
            )
            raise
