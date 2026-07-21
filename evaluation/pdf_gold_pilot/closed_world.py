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
from document_model import PageRole

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
