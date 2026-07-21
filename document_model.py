"""Stable intermediate document model for PDF extraction and semantic review."""
from __future__ import annotations

import hashlib
import math
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParseStatus(str, Enum):
    parsed = "parsed"
    requires_ocr = "requires_ocr"
    low_confidence = "low_confidence"
    failed = "failed"


class PageRole(str, Enum):
    teacher_guide = "teacher_guide"
    student_worksheet = "student_worksheet"
    answer_key = "answer_key"
    reference_material = "reference_material"
    mixed = "mixed"
    unknown = "unknown"


class BlockSemanticRole(str, Enum):
    teacher_instruction = "teacher_instruction"
    student_prompt = "student_prompt"
    response_area = "response_area"
    answer_key_content = "answer_key_content"
    example = "example"
    rubric = "rubric"
    standard = "standard"
    table_or_reference_value = "table_or_reference_value"
    navigation_or_metadata = "navigation_or_metadata"
    decorative_or_irrelevant = "decorative_or_irrelevant"
    unknown = "unknown"


class AnswerRegionStatus(str, Enum):
    detected = "detected"
    approved = "approved"
    missing = "missing"
    low_confidence = "low_confidence"
    side_panel = "side_panel"


class ReviewStatus(str, Enum):
    auto_approved = "auto_approved"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"
    hidden = "hidden"


class SourceKind(str, Enum):
    native_pdf = "native_pdf"
    paddleocr = "paddleocr"
    pdf_geometry = "pdf_geometry"


def _validated_bbox(value: list[float] | None, label: str) -> list[float] | None:
    if value is None:
        return None
    if len(value) != 4:
        raise ValueError(f"{label} must contain [x0, y0, x1, y1]")
    result = [float(item) for item in value]
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{label} must contain finite coordinates")
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError(f"{label} must have positive width and height")
    return result


class DocumentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(ge=0)
    reading_order: int = Field(ge=0)
    text: str = ""
    block_label: str = "text"
    bbox: list[float]
    polygon: list[list[float]] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: SourceKind
    semantic_role: BlockSemanticRole = BlockSemanticRole.unknown

    @model_validator(mode="after")
    def validate_geometry(self):
        self.bbox = _validated_bbox(self.bbox, "bbox") or []
        if self.polygon is not None:
            if len(self.polygon) < 4:
                raise ValueError("polygon must contain at least four points")
            for point in self.polygon:
                if len(point) != 2 or not all(math.isfinite(float(value)) for value in point):
                    raise ValueError("polygon points must contain finite x/y coordinates")
        return self


class DocumentPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0)
    width_points: float = Field(gt=0)
    height_points: float = Field(gt=0)
    rotation: Literal[0, 90, 180, 270] = 0
    native_text_exists: bool = False
    ocr_required: bool = False
    extraction_status: ParseStatus = ParseStatus.parsed
    page_role: PageRole = PageRole.unknown
    role_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = True
    paddle_block_count: int = Field(default=0, ge=0)
    block_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    legacy_question_id: int = Field(ge=1)
    label: str | None = None
    prompt_text: str
    page_index: int = Field(ge=0)
    page_role: PageRole
    prompt_bbox: list[float] | None = None
    answer_bbox: list[float] | None = None
    response_type: str = "short_text"
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: ReviewStatus = ReviewStatus.needs_review
    answer_region_status: AnswerRegionStatus = AnswerRegionStatus.missing
    source_blocks: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_regions(self):
        self.prompt_bbox = _validated_bbox(self.prompt_bbox, "prompt_bbox")
        self.answer_bbox = _validated_bbox(self.answer_bbox, "answer_bbox")
        if self.answer_region_status in {AnswerRegionStatus.detected, AnswerRegionStatus.approved}:
            if self.answer_bbox is None:
                raise ValueError("detected or approved answer regions require answer_bbox")
        return self

    @property
    def approved(self) -> bool:
        return self.review_status in {ReviewStatus.auto_approved, ReviewStatus.approved}


class IntermediateDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    title: str
    parser: str
    status: ParseStatus
    document_id: str | None = None
    source_sha256: str | None = None
    parser_version: str | None = None
    pages: list[DocumentPage]
    blocks: list[DocumentBlock]
    tasks: list[DocumentTask]
    warnings: list[str] = Field(default_factory=list)
    processing_ms: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_provenance(self):
        page_indexes = {page.page_index for page in self.pages}
        block_by_id = {block.id: block for block in self.blocks}
        if len(block_by_id) != len(self.blocks):
            raise ValueError("block IDs must be unique")
        if len({task.id for task in self.tasks}) != len(self.tasks):
            raise ValueError("task IDs must be unique")
        if len({task.legacy_question_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("legacy question IDs must be unique")
        for page in self.pages:
            missing = [block_id for block_id in page.block_ids if block_id not in block_by_id]
            if missing:
                raise ValueError(f"page {page.page_index} references unknown blocks: {missing}")
        for block in self.blocks:
            if block.page_index not in page_indexes:
                raise ValueError(f"block {block.id} references unknown page")
        for task in self.tasks:
            if task.page_index not in page_indexes:
                raise ValueError(f"task {task.id} references unknown page")
            for block_id in task.source_blocks:
                block = block_by_id.get(block_id)
                if block is None or block.page_index != task.page_index:
                    raise ValueError(f"task {task.id} has invalid source block {block_id}")
        return self


def stable_task_id(page_index: int, label: str | None, source_blocks: list[str], prompt_text: str) -> str:
    """Create a deterministic, collision-resistant ID without exposing document text."""
    seed = "\x1f".join(
        [str(page_index), (label or "").lower(), *source_blocks, prompt_text.strip().lower()]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    readable = "".join(ch.lower() for ch in (label or "") if ch.isalnum())[:12]
    return f"q{readable}-{digest}" if readable else f"q-{digest}"
