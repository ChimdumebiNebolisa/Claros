"""Authoritative, validated document contract for worksheet understanding.

The document model is intentionally immutable with respect to student work.
It owns physical evidence and task relationships; draft, confirmation, and
write state live in ``session_service`` only.
"""
from __future__ import annotations

import hashlib
import math
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CANONICAL_DOCUMENT_VERSION = 2
_PHYSICAL_RESPONSE_BLOCK_LABELS = {
    "answer_line",
    "bounded_box",
    "checkbox",
    "form_field",
    "writable_area",
}
_RESPONSE_REGION_TYPE_BY_PHYSICAL_LABEL = {
    "answer_line": "answer_line",
    "bounded_box": "bounded_box",
    "checkbox": "checkbox",
    "form_field": "form_field",
    "writable_area": "writable_area",
}
_TASK_SHAPED_SOURCE_PROMPT = re.compile(
    r"^\s*(?:\(?[1-9][0-9]*[.)]|question\s+[1-9][0-9]*\b)\s*\S",
    re.IGNORECASE,
)
_NUMBERED_SOURCE_PROMPT_LABEL = re.compile(r"^\s*\(?([1-9][0-9]*)[.)]\s+\S")
_NUMERIC_CHOICE_SOURCE_TEXT = re.compile(r"^\s*[1-9][0-9]?\s*[.)]\s+\S")
_CHOICE_SOURCE_PROMPT_CUE = re.compile(
    r"\b(?:choose|select|option|choice|correct\s+answer)\b",
    re.IGNORECASE,
)
_TASK_INSTRUCTION_SOURCE_START = re.compile(
    r"^\s*(?:answer|calculate|choose|circle|compare|complete|describe|draw|"
    r"explain|fill|find|identify|label|list|read|record|select|solve|state|use|write)\b",
    re.IGNORECASE,
)
_EXPLICIT_SOURCE_RESPONSE_LABEL = re.compile(
    r"^\s*(?:(?:(?:your|final|student)\s+)?(?:answer|response)|"
    r"write\s+(?:your\s+)?answer|show\s+(?:your\s+)?work)\s*:\s*$",
    re.IGNORECASE,
)


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
    legacy_parser = "legacy_parser"


class CoordinateSpace(str, Enum):
    """Coordinates are PDF points except for explicitly quarantined legacy data."""

    pdf_points = "pdf_points"
    normalized_legacy = "normalized_legacy"


class ResponseType(str, Enum):
    short_text = "short_text"
    long_text = "long_text"
    numeric = "numeric"
    choice = "choice"
    checkbox = "checkbox"
    drawing = "drawing"
    table = "table"
    unknown = "unknown"


class ResponseRegionType(str, Enum):
    answer_line = "answer_line"
    bounded_box = "bounded_box"
    checkbox = "checkbox"
    form_field = "form_field"
    writable_area = "writable_area"
    unknown = "unknown"


class ResponseSafety(str, Enum):
    """Whether deterministic code may use a physical response region."""

    approved = "approved"
    needs_review = "needs_review"
    unsafe = "unsafe"


class EvidenceStatus(str, Enum):
    """Whether a task retains traceable source evidence from the worksheet."""

    verified = "verified"
    legacy_unverified = "legacy_unverified"


class AnswerRegionStatus(str, Enum):
    """Deprecated projection status retained only while legacy callers migrate."""

    detected = "detected"
    approved = "approved"
    missing = "missing"
    low_confidence = "low_confidence"
    side_panel = "side_panel"


class TaskResponseRole(str, Enum):
    answer = "answer"
    explanation = "explanation"
    show_work = "show_work"
    choice = "choice"
    other = "other"


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


def _bbox_contains(container: list[float], candidate: list[float]) -> bool:
    """Return whether a candidate rectangle stays entirely within its evidence."""
    return (
        container[0] <= candidate[0]
        and container[1] <= candidate[1]
        and candidate[2] <= container[2]
        and candidate[3] <= container[3]
    )


def _bboxes_overlap(first: list[float], second: list[float]) -> bool:
    """Treat shared interior as overlap; touching borders are distinct regions."""
    return (
        max(first[0], second[0]) < min(first[2], second[2])
        and max(first[1], second[1]) < min(first[3], second[3])
    )


class DocumentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=240)
    page_index: int = Field(ge=0)
    reading_order: int = Field(ge=0)
    text: str = ""
    block_label: str = "text"
    bbox: list[float] | None = None
    polygon: list[list[float]] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: SourceKind
    semantic_role: BlockSemanticRole = BlockSemanticRole.unknown

    @model_validator(mode="after")
    def validate_geometry(self):
        self.bbox = _validated_bbox(self.bbox, "bbox")
        if self.polygon is not None:
            if len(self.polygon) < 4:
                raise ValueError("polygon must contain at least four points")
            for point in self.polygon:
                if len(point) != 2 or not all(math.isfinite(float(value)) for value in point):
                    raise ValueError("polygon points must contain finite x/y coordinates")
        return self


def source_prompt_text(blocks: list[DocumentBlock]) -> str:
    """Reconstruct task wording from ordered physical source blocks only."""

    def key(block: DocumentBlock) -> tuple[int, int, float, float, str]:
        bbox = block.bbox or [float("inf"), float("inf"), float("inf"), float("inf")]
        return (block.page_index, block.reading_order, bbox[1], bbox[0], block.id)

    return "\n".join(block.text.strip() for block in sorted(blocks, key=key) if block.text.strip())


class DocumentPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0)
    width_points: float = Field(gt=0)
    height_points: float = Field(gt=0)
    coordinate_space: CoordinateSpace = CoordinateSpace.pdf_points
    rotation: Literal[0, 90, 180, 270] = 0
    display_transform_required: bool = False
    native_text_exists: bool = False
    ocr_required: bool = False
    extraction_status: ParseStatus = ParseStatus.parsed
    page_role: PageRole = PageRole.unknown
    role_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = True
    paddle_block_count: int = Field(default=0, ge=0)
    block_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimensions(self):
        if not math.isfinite(self.width_points) or not math.isfinite(self.height_points):
            raise ValueError("page dimensions must be finite")
        return self


def page_has_reliable_native_write_evidence(page: DocumentPage) -> bool:
    """Whether a page may contribute deterministic student write authority."""
    return (
        page.coordinate_space == CoordinateSpace.pdf_points
        and page.native_text_exists
        and not page.ocr_required
        and page.extraction_status == ParseStatus.parsed
        and not page.needs_review
    )


class DocumentResponseRegion(BaseModel):
    """One physical response destination with its own stable identity."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=240)
    page_index: int = Field(ge=0)
    bbox: list[float]
    region_type: ResponseRegionType = ResponseRegionType.unknown
    response_type: ResponseType = ResponseType.short_text
    safety: ResponseSafety = ResponseSafety.needs_review
    confidence: float = Field(ge=0.0, le=1.0)
    source_block_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_region(self):
        self.bbox = _validated_bbox(self.bbox, "response region bbox") or []
        if any(not source_id.strip() for source_id in self.source_block_ids):
            raise ValueError("response region source_block_ids must be non-empty")
        if len(self.source_block_ids) != len(set(self.source_block_ids)):
            raise ValueError("response region source_block_ids must be unique")
        return self


class TaskResponseLink(BaseModel):
    """A task-to-region relation; relation role is distinct from region type."""

    model_config = ConfigDict(extra="forbid")

    response_region_id: str = Field(min_length=1, max_length=240)
    role: TaskResponseRole = TaskResponseRole.answer
    order: int = Field(ge=0)
    choice_id: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_choice_relation(self):
        if self.role == TaskResponseRole.choice and not self.choice_id:
            raise ValueError("choice response links require choice_id")
        if self.role != TaskResponseRole.choice and self.choice_id is not None:
            raise ValueError("only choice response links may reference choice_id")
        return self


class DocumentChoice(BaseModel):
    """A structured selectable choice tied to physical source evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=240)
    order: int = Field(ge=0)
    label: str | None = None
    text: str
    source_block_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_choice(self):
        if not self.text.strip():
            raise ValueError("choice text must be non-empty")
        if any(not source_id.strip() for source_id in self.source_block_ids):
            raise ValueError("choice source_block_ids must be non-empty")
        if len(self.source_block_ids) != len(set(self.source_block_ids)):
            raise ValueError("choice source_block_ids must be unique")
        return self


class DocumentTask(BaseModel):
    """Stable task identity and relations, never mutable student response state."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    legacy_question_id: int = Field(ge=1)
    order: int = Field(ge=0)
    label: str | None = None
    prompt_text: str
    anchor_page_index: int = Field(ge=0)
    page_role: PageRole = PageRole.unknown
    prompt_block_ids: list[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus = EvidenceStatus.verified
    parent_task_id: str | None = None
    subpart: str | None = None
    choices: list[DocumentChoice] = Field(default_factory=list)
    response_links: list[TaskResponseLink] = Field(default_factory=list)
    side_panel_fallback: bool = False
    response_type: ResponseType = ResponseType.short_text
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: ReviewStatus = ReviewStatus.needs_review

    @model_validator(mode="after")
    def validate_task(self):
        if not self.prompt_text.strip():
            raise ValueError("task prompt_text must be non-empty")
        if not self.prompt_block_ids and self.evidence_status != EvidenceStatus.legacy_unverified:
            raise ValueError("task prompt_block_ids require verified source evidence")
        if any(not block_id.strip() for block_id in self.prompt_block_ids):
            raise ValueError("task prompt_block_ids must be non-empty")
        if self.parent_task_id == "":
            raise ValueError("task parent_task_id must be non-empty when supplied")
        if self.evidence_status == EvidenceStatus.legacy_unverified:
            if self.prompt_block_ids:
                raise ValueError("legacy-unverified tasks cannot claim prompt block evidence")
            if self.response_links:
                raise ValueError("legacy-unverified tasks cannot claim physical response evidence")
            if not self.side_panel_fallback:
                raise ValueError("legacy-unverified tasks require side_panel_fallback")
        if len(self.prompt_block_ids) != len(set(self.prompt_block_ids)):
            raise ValueError("task prompt_block_ids must be unique")
        response_ids = [link.response_region_id for link in self.response_links]
        if len(response_ids) != len(set(response_ids)):
            raise ValueError("task response links must be unique")
        response_orders = [link.order for link in self.response_links]
        if len(response_orders) != len(set(response_orders)):
            raise ValueError("task response-link order must be unique")
        choice_ids = [choice.id for choice in self.choices]
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("task choice IDs must be unique")
        choice_orders = [choice.order for choice in self.choices]
        if len(choice_orders) != len(set(choice_orders)):
            raise ValueError("task choice order must be unique")
        choice_link_ids = [
            link.choice_id
            for link in self.response_links
            if link.role == TaskResponseRole.choice
        ]
        if any(choice_id not in choice_ids for choice_id in choice_link_ids):
            raise ValueError("choice response link references an unknown choice")
        if len(choice_link_ids) != len(set(choice_link_ids)):
            raise ValueError("choice response links must be one-to-one")
        if choice_link_ids and set(choice_link_ids) != set(choice_ids):
            raise ValueError("choice response links must cover every structured choice")
        if self.response_links and not any(
            link.role == TaskResponseRole.answer for link in self.response_links
        ) and not self.side_panel_fallback:
            raise ValueError("tasks without an answer response link require side_panel_fallback")
        if not self.response_links and not self.side_panel_fallback:
            raise ValueError("zero-response task requires explicit side_panel_fallback")
        return self

    @property
    def approved(self) -> bool:
        return self.review_status in {ReviewStatus.auto_approved, ReviewStatus.approved}

    @property
    def source_blocks(self) -> list[str]:
        """Deprecated read-only alias for legacy adapters and diagnostics."""
        return list(self.prompt_block_ids)


def task_has_student_write_role(task: DocumentTask, page: DocumentPage) -> bool:
    """Only an explicitly classified student worksheet may receive a write."""
    return (
        page.page_role == PageRole.student_worksheet
        and task.page_role == PageRole.student_worksheet
    )


def _native_prompt_looks_like_numeric_choice(
    prompt: DocumentBlock,
    all_blocks: list[DocumentBlock],
) -> bool:
    """Keep a numbered choice from becoming a physical-write prompt."""
    label = _NUMBERED_SOURCE_PROMPT_LABEL.match(prompt.text)
    if label is None or prompt.bbox is None or not _NUMERIC_CHOICE_SOURCE_TEXT.match(prompt.text):
        return False
    prompt_number = int(label.group(1))
    for candidate in all_blocks:
        candidate_label = _NUMBERED_SOURCE_PROMPT_LABEL.match(candidate.text)
        if (
            candidate.id == prompt.id
            or candidate.source != SourceKind.native_pdf
            or candidate.page_index != prompt.page_index
            or candidate.bbox is None
            or candidate.bbox[1] >= prompt.bbox[1] - 2
            or candidate_label is None
            or not _CHOICE_SOURCE_PROMPT_CUE.search(candidate.text)
        ):
            continue
        if prompt_number <= int(candidate_label.group(1)) or prompt.bbox[0] >= candidate.bbox[0] + 12:
            return True
        if any(
            block.id not in {candidate.id, prompt.id}
            and block.source == SourceKind.native_pdf
            and block.page_index == prompt.page_index
            and block.bbox is not None
            and candidate.bbox[1] + 2 < block.bbox[1] < prompt.bbox[1] - 2
            and abs(block.bbox[0] - prompt.bbox[0]) <= 12
            and _NUMERIC_CHOICE_SOURCE_TEXT.match(block.text)
            for block in all_blocks
        ):
            return True
    return False


def _native_prompt_text_has_competing_instruction(text: str) -> bool:
    """Reject a source line that merges multiple imperative tasks."""
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
            and _TASK_INSTRUCTION_SOURCE_START.match(suffix)
            and not _EXPLICIT_SOURCE_RESPONSE_LABEL.match(suffix)
        ):
            return True
    return False


def _native_prompt_blocks_describe_one_task(blocks: list[DocumentBlock]) -> bool:
    """Match the extractor's conservative wrapped-prompt continuity rule."""
    if len(blocks) == 1:
        return not _native_prompt_text_has_competing_instruction(blocks[0].text)
    first = blocks[0]
    if first.bbox is None or not _TASK_SHAPED_SOURCE_PROMPT.match(first.text):
        return False
    previous = first
    for continuation in blocks[1:]:
        if (
            continuation.bbox is None
            or continuation.page_index != first.page_index
            or previous.text.rstrip().endswith((".", "?", "!", ":"))
            or _TASK_SHAPED_SOURCE_PROMPT.match(continuation.text)
            or _TASK_INSTRUCTION_SOURCE_START.match(continuation.text)
            or not re.match(r"^\s*(?:[a-z]|[([])", continuation.text)
            or continuation.text.rstrip().endswith(":")
            or continuation.bbox[1] < previous.bbox[3] - 2
            or continuation.bbox[1] - previous.bbox[3] > 24
            or continuation.bbox[0] < first.bbox[0] - 4
            or continuation.bbox[0] > first.bbox[0] + 48
        ):
            return False
        previous = continuation
    return True


def task_has_native_local_prompt_evidence(
    task: DocumentTask,
    region: DocumentResponseRegion,
    block_by_id: dict[str, DocumentBlock],
) -> bool:
    """Return whether a task's write association has native, local prompt proof.

    OCR text may support understanding, but it cannot authorize a physical
    write destination. The selected source prompt must be a numbered/question
    task on the same page, except for a directly adjacent colon-ended form
    label. Export applies the same proof to freshly extracted source blocks.
    """
    if (
        task.evidence_status != EvidenceStatus.verified
        or not task.prompt_block_ids
        or task.anchor_page_index != region.page_index
    ):
        return False
    local_prompt_blocks: list[DocumentBlock] = []
    for block_id in task.prompt_block_ids:
        block = block_by_id.get(block_id)
        if (
            block is None
            or block.source != SourceKind.native_pdf
            or block.page_index != region.page_index
            or block.bbox is None
            or not block.text.strip()
        ):
            return False
        local_prompt_blocks.append(block)
    if not _native_prompt_blocks_describe_one_task(local_prompt_blocks):
        return False
    if any(
        _native_prompt_looks_like_numeric_choice(block, list(block_by_id.values()))
        for block in local_prompt_blocks
    ):
        return False
    task_shaped_blocks = [
        block for block in local_prompt_blocks if _TASK_SHAPED_SOURCE_PROMPT.match(block.text)
    ]
    if len(task_shaped_blocks) > 1:
        return False
    if task_shaped_blocks:
        return True
    return any(
        (
            block.text.rstrip().endswith(":")
            and region.bbox[0] >= block.bbox[2] - 15
            and abs(
                (region.bbox[1] + region.bbox[3]) / 2
                - (block.bbox[1] + block.bbox[3]) / 2
            )
            <= 20
        )
        for block in local_prompt_blocks
    )


def _upgrade_document_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the prior one-box document structure without inventing evidence.

    Older task records did not preserve enough provenance to re-create physical
    response evidence safely. Their coordinates remain unavailable to the v2
    document and every migrated response uses the side panel. This prevents
    synthetic source/candidate IDs or legacy rectangles from acquiring write
    authority.
    """
    data = dict(payload)
    if "schema_version" not in data:
        current_task_shape = any(
            (isinstance(task, dict) and "prompt_block_ids" in task)
            or hasattr(task, "prompt_block_ids")
            for task in data.get("tasks") or []
        )
        data["schema_version"] = (
            CANONICAL_DOCUMENT_VERSION
            if current_task_shape
            else int(data.get("version", 1) or 1)
        )
        data.pop("version", None)
    if int(data["schema_version"]) >= CANONICAL_DOCUMENT_VERSION:
        return data

    upgraded_tasks: list[dict[str, Any]] = []
    generated_legacy_ids: set[str] = set()
    for raw_task in data.get("tasks") or []:
        task = dict(raw_task)
        # A pre-v2 task did not express an auditable prompt/source relation.
        # Preserve its historical wording only as quarantined legacy metadata;
        # never claim its old source list or response rectangle is canonical
        # physical evidence.
        prompt_ids: list[str] = []
        evidence_status = EvidenceStatus.legacy_unverified.value
        prompt_text = str(task.get("prompt_text") or "").strip()
        if not prompt_text:
            raise ValueError("legacy task lacks prompt text")
        generated_task_id, generated_legacy_id = legacy_quarantine_task_identity(
            page_index=int(task.get("page_index", 0) or 0),
            label=task.get("label"),
            prompt_text=prompt_text,
            parent_task_id=task.get("parent_task_id"),
            subpart=task.get("subpart"),
        )
        raw_task_id = task.get("id")
        if raw_task_id is None:
            if generated_task_id in generated_legacy_ids:
                raise ValueError("id-less legacy tasks require distinct source fingerprints")
            generated_legacy_ids.add(generated_task_id)
            task_id = generated_task_id
        else:
            task_id = str(raw_task_id)
        upgraded_tasks.append(
            {
                "id": task_id,
                "legacy_question_id": (
                    task["legacy_question_id"]
                    if task.get("legacy_question_id") is not None
                    else generated_legacy_id
                ),
                "order": 0,
                "label": task.get("label"),
                "prompt_text": prompt_text,
                "anchor_page_index": task.get("page_index", 0),
                "page_role": task.get("page_role", PageRole.unknown.value),
                "prompt_block_ids": prompt_ids,
                "evidence_status": evidence_status,
                "parent_task_id": None,
                "subpart": None,
                "choices": [],
                "response_links": [],
                "side_panel_fallback": True,
                "response_type": task.get("response_type", "short_text"),
                "confidence": task.get("confidence", 0.0),
                "review_status": task.get("review_status", ReviewStatus.needs_review.value),
            }
        )
    upgraded_tasks.sort(
        key=lambda task: (
            int(task["anchor_page_index"]),
            int(task["legacy_question_id"]),
            str(task["id"]),
        )
    )
    for order, task in enumerate(upgraded_tasks):
        task["order"] = order
    data["response_regions"] = []
    data["tasks"] = upgraded_tasks
    data["schema_version"] = CANONICAL_DOCUMENT_VERSION
    warnings = list(data.get("warnings") or [])
    if "canonical_document_v2_migrated_side_panel_only" not in warnings:
        warnings.append("canonical_document_v2_migrated_side_panel_only")
    data["warnings"] = warnings
    return data


class IntermediateDocument(BaseModel):
    """The one persisted document contract used by production and evaluation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = CANONICAL_DOCUMENT_VERSION
    title: str
    parser: str
    status: ParseStatus
    document_id: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    parser_version: str | None = None
    pages: list[DocumentPage] = Field(min_length=1)
    blocks: list[DocumentBlock]
    response_regions: list[DocumentResponseRegion] = Field(default_factory=list)
    tasks: list[DocumentTask]
    warnings: list[str] = Field(default_factory=list)
    processing_ms: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_document(cls, value: Any):
        if isinstance(value, dict):
            return _upgrade_document_payload(value)
        return value

    @model_validator(mode="after")
    def validate_provenance(self):
        if self.schema_version != CANONICAL_DOCUMENT_VERSION:
            raise ValueError(f"unsupported document schema version: {self.schema_version}")
        page_indexes = {page.page_index for page in self.pages}
        if len(page_indexes) != len(self.pages):
            raise ValueError("page indexes must be unique")
        if page_indexes != set(range(len(self.pages))):
            raise ValueError("page indexes must be contiguous from zero")
        block_by_id = {block.id: block for block in self.blocks}
        if len(block_by_id) != len(self.blocks):
            raise ValueError("block IDs must be unique")
        region_by_id = {region.id: region for region in self.response_regions}
        if len(region_by_id) != len(self.response_regions):
            raise ValueError("response region IDs must be unique")
        task_by_id = {task.id: task for task in self.tasks}
        if len(task_by_id) != len(self.tasks):
            raise ValueError("task IDs must be unique")
        if len({task.legacy_question_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("legacy question IDs must be unique")
        if len({task.order for task in self.tasks}) != len(self.tasks):
            raise ValueError("task order must be unique")
        choice_ids = [choice.id for task in self.tasks for choice in task.choices]
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("choice IDs must be unique across the document")
        attached_region_ids = [
            link.response_region_id for task in self.tasks for link in task.response_links
        ]
        if len(attached_region_ids) != len(set(attached_region_ids)):
            raise ValueError("response regions may belong to only one task")
        region_source_owners: dict[str, str] = {}
        for region in self.response_regions:
            for source_block_id in region.source_block_ids:
                owner = region_source_owners.get(source_block_id)
                if owner is not None and owner != region.id:
                    raise ValueError(
                        "physical response source blocks may belong to only one response region"
                    )
                region_source_owners[source_block_id] = region.id

        for page in self.pages:
            if len(page.block_ids) != len(set(page.block_ids)):
                raise ValueError(f"page {page.page_index} has duplicate block IDs")
            missing = [block_id for block_id in page.block_ids if block_id not in block_by_id]
            if missing:
                raise ValueError(f"page {page.page_index} references unknown blocks: {missing}")
            foreign = [
                block_id
                for block_id in page.block_ids
                if block_by_id[block_id].page_index != page.page_index
            ]
            if foreign:
                raise ValueError(f"page {page.page_index} references blocks on another page: {foreign}")
        for block in self.blocks:
            if block.page_index not in page_indexes:
                raise ValueError(f"block {block.id} references unknown page")
            owning_page = next(page for page in self.pages if page.page_index == block.page_index)
            if block.id not in owning_page.block_ids:
                raise ValueError(f"block {block.id} is missing from its owning page")
            width_limit = (
                1.0
                if owning_page.coordinate_space == CoordinateSpace.normalized_legacy
                else owning_page.width_points
            )
            height_limit = (
                1.0
                if owning_page.coordinate_space == CoordinateSpace.normalized_legacy
                else owning_page.height_points
            )
            if block.bbox is not None:
                x0, y0, x1, y1 = block.bbox
                if x0 < 0 or y0 < 0 or x1 > width_limit or y1 > height_limit:
                    raise ValueError(f"block {block.id} is outside its page bounds")
            if block.polygon is not None and any(
                x < 0 or y < 0 or x > width_limit or y > height_limit
                for x, y in block.polygon
            ):
                raise ValueError(f"block {block.id} polygon is outside its page bounds")
        for region in self.response_regions:
            if region.page_index not in page_indexes:
                raise ValueError(f"response region {region.id} references unknown page")
            page = self.page(region.page_index)
            x0, y0, x1, y1 = region.bbox
            width_limit = 1.0 if page.coordinate_space == CoordinateSpace.normalized_legacy else page.width_points
            height_limit = 1.0 if page.coordinate_space == CoordinateSpace.normalized_legacy else page.height_points
            if x0 < 0 or y0 < 0 or x1 > width_limit or y1 > height_limit:
                raise ValueError(f"response region {region.id} is outside its page bounds")
            for block_id in region.source_block_ids:
                block = block_by_id.get(block_id)
                if block is None:
                    raise ValueError(f"response region {region.id} references unknown source block {block_id}")
                if block.page_index != region.page_index:
                    raise ValueError(
                        f"response region {region.id} source block must be on its own page"
                    )
            if region.safety == ResponseSafety.approved:
                if page.rotation != 0 or page.display_transform_required:
                    raise ValueError(
                        f"approved response region {region.id} cannot use a page requiring display transform"
                    )
                evidence_blocks = [block_by_id[block_id] for block_id in region.source_block_ids]
                physical_sources = [
                    block
                    for block in evidence_blocks
                    if (
                        block.source == SourceKind.pdf_geometry
                        or (
                            page.coordinate_space == CoordinateSpace.normalized_legacy
                            and block.source == SourceKind.legacy_parser
                        )
                    )
                    and block.semantic_role == BlockSemanticRole.response_area
                    and block.block_label in _PHYSICAL_RESPONSE_BLOCK_LABELS
                    and block.bbox is not None
                    and _RESPONSE_REGION_TYPE_BY_PHYSICAL_LABEL.get(block.block_label)
                    == region.region_type.value
                ]
                if not physical_sources:
                    raise ValueError(
                        f"approved response region {region.id} lacks physical response-area evidence"
                    )
                if not any(
                    _bbox_contains(block.bbox, region.bbox)
                    for block in physical_sources
                    if block.bbox is not None
                ):
                    raise ValueError(
                        f"approved response region {region.id} does not fit within its physical evidence"
                    )
        approved_regions = [
            region
            for region in self.response_regions
            if region.safety == ResponseSafety.approved
        ]
        for index, first in enumerate(approved_regions):
            for second in approved_regions[index + 1 :]:
                if first.page_index == second.page_index and _bboxes_overlap(first.bbox, second.bbox):
                    raise ValueError("approved response regions may not overlap")
        for task in self.tasks:
            if task.anchor_page_index not in page_indexes:
                raise ValueError(f"task {task.id} references unknown anchor page")
            if task.parent_task_id == task.id:
                raise ValueError(f"task {task.id} cannot parent itself")
            if task.parent_task_id and task.parent_task_id not in task_by_id:
                raise ValueError(f"task {task.id} references unknown parent task")
            for block_id in task.prompt_block_ids:
                if block_id not in block_by_id:
                    raise ValueError(f"task {task.id} references unknown prompt block {block_id}")
            if task.evidence_status == EvidenceStatus.legacy_unverified and task.prompt_block_ids:
                raise ValueError(f"task {task.id} has legacy-unverified prompt evidence")
            if task.evidence_status == EvidenceStatus.verified:
                derived_prompt = source_prompt_text(
                    [block_by_id[block_id] for block_id in task.prompt_block_ids]
                )
                if not derived_prompt:
                    raise ValueError(f"task {task.id} has no source-backed prompt text")
                if task.prompt_text != derived_prompt:
                    raise ValueError(f"task {task.id} prompt_text must match its source blocks")
            for choice in task.choices:
                for block_id in choice.source_block_ids:
                    if block_id not in block_by_id:
                        raise ValueError(f"choice {choice.id} references unknown source block {block_id}")
                derived_choice_text = source_prompt_text(
                    [block_by_id[block_id] for block_id in choice.source_block_ids]
                )
                if not derived_choice_text:
                    raise ValueError(f"choice {choice.id} has no source-backed text")
                if choice.text != derived_choice_text:
                    raise ValueError(f"choice {choice.id} text must match its source blocks")
                if choice.label is not None and choice.label != derived_choice_text:
                    raise ValueError(f"choice {choice.id} label must match its source blocks")
            for link in task.response_links:
                region = region_by_id.get(link.response_region_id)
                if region is None:
                    raise ValueError(f"task {task.id} references unknown response region {link.response_region_id}")
                if region.region_type == ResponseRegionType.checkbox and link.role != TaskResponseRole.choice:
                    raise ValueError("checkbox response regions require choice response links")
                if link.role == TaskResponseRole.choice and region.region_type != ResponseRegionType.checkbox:
                    raise ValueError("choice response links require checkbox response regions")
                if region.safety != ResponseSafety.approved and not task.side_panel_fallback:
                    raise ValueError(
                        f"task {task.id} needs side_panel_fallback for non-approved response region"
                    )

        for task in self.tasks:
            seen: set[str] = set()
            current = task
            while current.parent_task_id:
                parent_id = current.parent_task_id
                if parent_id in seen:
                    raise ValueError("task parent relationships must be acyclic")
                seen.add(parent_id)
                current = task_by_id[parent_id]
        return self

    def response_region(self, response_region_id: str) -> DocumentResponseRegion:
        for region in self.response_regions:
            if region.id == response_region_id:
                return region
        raise KeyError(response_region_id)

    def task(self, task_id: str) -> DocumentTask:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)

    def page(self, page_index: int) -> DocumentPage:
        for page in self.pages:
            if page.page_index == page_index:
                return page
        raise KeyError(page_index)

    def normalized_region(self, region: DocumentResponseRegion) -> dict[str, float]:
        page = self.page(region.page_index)
        x0, y0, x1, y1 = region.bbox
        if page.coordinate_space == CoordinateSpace.normalized_legacy:
            return {
                "x": round(x0, 6),
                "y": round(y0, 6),
                "width": round(x1 - x0, 6),
                "height": round(y1 - y0, 6),
            }
        return {
            "x": round(x0 / page.width_points, 6),
            "y": round(y0 / page.height_points, 6),
            "width": round((x1 - x0) / page.width_points, 6),
            "height": round((y1 - y0) / page.height_points, 6),
        }

    def task_views(self, *, include_unapproved: bool = True, student_safe: bool = True) -> list[dict[str, Any]]:
        """Create a compatibility/API projection without becoming a second model.

        The projection deliberately omits unsafe geometry from student-facing
        payloads while preserving a stable target ID and the side-panel route.
        """
        result: list[dict[str, Any]] = []
        block_by_id = {block.id: block for block in self.blocks}
        for task in sorted(self.tasks, key=lambda item: item.order):
            if not include_unapproved and not task.approved:
                continue
            links = sorted(task.response_links, key=lambda item: item.order)
            response_views = []
            approved_answer_region: DocumentResponseRegion | None = None
            for link in links:
                region = self.response_region(link.response_region_id)
                # A checkbox is a selection control, not a text box. The
                # canonical contract can represent historical reviewed data,
                # but student-facing targets remain side-panel-only until a
                # deterministic mark renderer exists.
                page = self.page(region.page_index)
                has_compatible_write_evidence = any(
                    block.source == SourceKind.pdf_geometry
                    and block.semantic_role == BlockSemanticRole.response_area
                    and block.bbox is not None
                    and _RESPONSE_REGION_TYPE_BY_PHYSICAL_LABEL.get(block.block_label)
                    == region.region_type.value
                    and _bbox_contains(block.bbox, region.bbox)
                    for block_id in region.source_block_ids
                    if (block := block_by_id.get(block_id)) is not None
                )
                safe_for_write = (
                    task.approved
                    and not task.side_panel_fallback
                    and region.safety == ResponseSafety.approved
                    and region.region_type != ResponseRegionType.checkbox
                    and page.coordinate_space == CoordinateSpace.pdf_points
                    and not page.display_transform_required
                    and page.rotation == 0
                    and page_has_reliable_native_write_evidence(page)
                    and task_has_student_write_role(task, page)
                    and task.anchor_page_index == region.page_index
                    and task_has_native_local_prompt_evidence(task, region, block_by_id)
                    and has_compatible_write_evidence
                )
                entry: dict[str, Any] = {
                    "id": region.id,
                    "task_id": task.id,
                    "role": link.role.value,
                    "order": link.order,
                    "choice_id": link.choice_id,
                    "page_index": region.page_index,
                    "page": region.page_index + 1,
                    "region_type": region.region_type.value,
                    "response_type": region.response_type.value,
                    "safety": region.safety.value,
                    "safe_for_write": safe_for_write,
                }
                if safe_for_write or not student_safe:
                    entry["bbox"] = region.bbox
                    entry["region"] = self.normalized_region(region)
                response_views.append(entry)
                if approved_answer_region is None and safe_for_write and link.role == TaskResponseRole.answer:
                    approved_answer_region = region
            visible_region = approved_answer_region
            if visible_region is None and not student_safe and links:
                visible_region = self.response_region(links[0].response_region_id)
            target_id = visible_region.id if visible_region is not None else f"{task.id}:side-panel"
            visible_normalized_region = (
                self.normalized_region(visible_region) if visible_region is not None else None
            )
            if visible_region is None:
                legacy_region_status = "side_panel" if task.side_panel_fallback else "missing"
            elif visible_region.safety == ResponseSafety.approved:
                legacy_region_status = "approved"
            else:
                legacy_region_status = "detected"
            result.append(
                {
                    # ``id`` remains a migration-only display/API alias. New
                    # code must use task_id and response target IDs.
                    "id": task.legacy_question_id,
                    "task_id": task.id,
                    "order": task.order,
                    # Labels/subparts originate in semantic or review input,
                    # not deterministic source identity. Student-facing UI
                    # uses the server-assigned physical order instead.
                    "label": task.label if not student_safe else None,
                    "text": task.prompt_text,
                    "page": task.anchor_page_index + 1,
                    "page_index": task.anchor_page_index,
                    "page_role": task.page_role.value,
                    "parent_task_id": task.parent_task_id,
                    "subpart": task.subpart if not student_safe else None,
                    "prompt_block_ids": task.prompt_block_ids,
                    "evidence_status": task.evidence_status.value,
                    "source_blocks": task.prompt_block_ids,
                    "choices": [choice.model_dump(mode="json") for choice in task.choices],
                    "response_regions": response_views,
                    "response_target_id": target_id,
                    "response_type": task.response_type.value,
                    "side_panel_fallback": task.side_panel_fallback,
                    "confidence": task.confidence,
                    "review_status": task.review_status.value,
                    "approved": task.approved,
                    # Compatibility values used only by the existing client.
                    "answer_region": visible_normalized_region,
                    "answer_region_status": legacy_region_status,
                    "needs_layout_review": task.review_status == ReviewStatus.needs_review,
                }
            )
        return result


def stable_task_id(page_index: int, source_blocks: list[str], prompt_text: str) -> str:
    """Create a task ID from deterministic source evidence, never model labels."""
    stable_sources = sorted(set(source_blocks))
    seed = "\x1f".join([str(page_index), *stable_sources, prompt_text.strip().lower()])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return f"q-{digest}"


def stable_response_region_id(task_id: str, source_block_ids: list[str]) -> str:
    """Create a stable region ID from deterministic physical evidence only."""
    seed = "\x1f".join([task_id, *sorted(set(source_block_ids))])
    return f"r-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


def legacy_quarantine_task_identity(
    *,
    page_index: int,
    label: str | None,
    prompt_text: str,
    parent_task_id: str | None = None,
    subpart: str | None = None,
) -> tuple[str, int]:
    """Derive a quarantined identity from stable historical text, never array order."""
    seed = "\x1f".join(
        [
            str(page_index),
            prompt_text.strip().lower(),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"legacy-task-{digest}", max(1, int(digest, 16))
