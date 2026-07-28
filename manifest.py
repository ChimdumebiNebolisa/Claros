"""Assignment lifecycle envelope around the authoritative canonical document."""
from __future__ import annotations

import json
import hashlib
import hmac
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_model import (
    CoordinateSpace,
    DocumentPage,
    DocumentTask,
    EvidenceStatus,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ResponseType,
    ReviewStatus,
    legacy_quarantine_task_identity,
)

MANIFEST_VERSION = 4
LEGACY_MANIFEST_VERSION = 1
CANONICAL_MANIFEST_NAME = "manifest.json"
_MANIFEST_HMAC_CONTEXT = b"claros/assignment-manifest/v1\0"

LayoutConfidence = Literal["high", "medium", "low", "manual"]

MIN_ANSWER_WIDTH = 24.0
MIN_ANSWER_HEIGHT = 18.0


class ManifestQuestion(BaseModel):
    """Legacy/API projection, never a persisted source of truth."""

    model_config = ConfigDict(extra="forbid")

    id: int
    task_id: str
    order: int = Field(ge=0)
    text: str
    label: str | None = None
    page: int = Field(ge=1)
    page_index: int = Field(ge=0)
    page_role: str = "unknown"
    parent_task_id: str | None = None
    subpart: str | None = None
    prompt_block_ids: list[str] = Field(default_factory=list)
    evidence_status: str = EvidenceStatus.verified.value
    source_blocks: list[str] = Field(default_factory=list)
    choices: list[dict] = Field(default_factory=list)
    response_regions: list[dict] = Field(default_factory=list)
    response_target_id: str
    response_type: str = "short_text"
    side_panel_fallback: bool = False
    confidence: float = 0.0
    review_status: str = "needs_review"
    approved: bool = False
    # Compatibility-only flattened values. They are regenerated from document.
    answer_region: dict[str, float] | None = None
    answer_region_status: str = "side_panel"
    needs_layout_review: bool = False


class AssignmentManifest(BaseModel):
    """Persisted assignment metadata plus exactly one canonical document."""

    model_config = ConfigDict(extra="forbid")

    version: int = MANIFEST_VERSION
    assignment_id: str
    title: str
    document: IntermediateDocument
    parse_status: str = "ok"  # ok | layout_review_required | unsupported_layout | requires_ocr
    parse_warnings: list[str] = Field(default_factory=list)
    parser: str = "legacy"
    review_mode: str = "direct"
    review_status: str = "unreviewed"
    assignment_capability_hash: str | None = None
    # Persisted manifests are authenticated by assignment_service. The model
    # allows an absent tag only for quarantined legacy side-panel records.
    integrity_hmac: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_payload(cls, value: Any):
        if not isinstance(value, dict):
            return value
        return migrate_manifest_data(value)

    @property
    def page_count(self) -> int:
        return len(self.document.pages)

    @property
    def questions(self) -> list[ManifestQuestion]:
        """Compatibility read view; callers must not mutate it as canonical state."""
        return [
            ManifestQuestion.model_validate(question)
            for question in self.document.task_views(student_safe=self.review_mode != "teacher")
        ]

    def to_questions_dict(self, *, approved_only: bool = False) -> list[dict]:
        return self.document.task_views(
            include_unapproved=not approved_only,
            student_safe=self.review_mode != "teacher",
        )

    def to_client_document(self, *, approved_only: bool = False) -> dict:
        """Return the canonical client contract without exposing unsafe geometry."""
        tasks = []
        for view in self.to_questions_dict(approved_only=approved_only):
            tasks.append(
                {
                    "id": view["task_id"],
                    "legacy_question_id": view["id"],
                    "order": view["order"],
                    "label": view["label"],
                    "prompt_text": view["text"],
                    "anchor_page_index": view["page_index"],
                    "page_role": view["page_role"],
                    "parent_task_id": view["parent_task_id"],
                    "subpart": view["subpart"],
                    "prompt_block_ids": view["prompt_block_ids"],
                    "evidence_status": view["evidence_status"],
                    "choices": view["choices"],
                    "response_regions": view["response_regions"],
                    "response_target_id": view["response_target_id"],
                    "response_type": view["response_type"],
                    "side_panel_fallback": view["side_panel_fallback"],
                    "confidence": view["confidence"],
                    "review_status": view["review_status"],
                    "approved": view["approved"],
                }
            )
        return {
            "schema_version": self.document.schema_version,
            "document_id": self.document.document_id,
            "title": self.title,
            "pages": [
                {
                    "page_index": page.page_index,
                    "page_role": page.page_role.value,
                    "width_points": page.width_points,
                    "height_points": page.height_points,
                }
                for page in self.document.pages
            ],
            "tasks": tasks,
        }

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return expires <= (now or datetime.now(timezone.utc))

    def model_dump_json(self, **kwargs: Any) -> str:
        return json.dumps(self.model_dump(mode="json", **kwargs), ensure_ascii=False)


def _require_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def normalize_bbox(raw: Any) -> list[float]:
    """Normalize a rectangle to [x0, y0, x1, y1] with finite positive size."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("bbox must be a list of four numbers [x0, y0, x1, y1]")
    coords = [_require_finite_number(raw[i], f"bbox[{i}]") for i in range(4)]
    x0, y0, x1, y1 = coords
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bbox must have positive width and height")
    return [x0, y0, x1, y1]


def validate_bbox_within_page(
    bbox: list[float],
    *,
    page_width: float,
    page_height: float,
    label: str = "bbox",
) -> list[float]:
    rect = normalize_bbox(bbox)
    x0, y0, x1, y1 = rect
    if x0 < 0 or y0 < 0 or x1 > page_width + 1e-6 or y1 > page_height + 1e-6:
        raise ValueError(f"{label} is outside page bounds")
    if (x1 - x0) < MIN_ANSWER_WIDTH or (y1 - y0) < MIN_ANSWER_HEIGHT:
        raise ValueError(f"{label} is below minimum dimensions")
    return rect


def _enum_value(enum_type, value: Any, default):
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return default


def legacy_document_from_questions(
    *,
    title: str,
    questions: list[dict],
    page_count: int = 1,
    parser: str = "legacy",
    document_id: str | None = None,
) -> IntermediateDocument:
    """Quarantine a flat historical projection into the canonical contract.

    The legacy parser did not preserve source-block IDs or PDF-point prompt
    geometry. This adapter keeps the historical prompt text as quarantined
    metadata, creates no synthetic source/candidate evidence, and routes every
    migrated response through the side panel.
    """
    raw_questions = [dict(item) for item in questions]
    max_page = max([page_count, *[int(item.get("page", 1) or 1) for item in raw_questions]], default=1)
    pages = [
        DocumentPage(
            page_index=index,
            width_points=1.0,
            height_points=1.0,
            coordinate_space=CoordinateSpace.normalized_legacy,
            page_role=PageRole.unknown,
            block_ids=[],
            needs_review=True,
        )
        for index in range(max(1, max_page))
    ]
    tasks: list[DocumentTask] = []
    idless_fingerprints: set[str] = set()

    for raw in raw_questions:
        page_index = max(0, int(raw.get("page_index", int(raw.get("page", 1) or 1) - 1)))
        if page_index >= len(pages):
            raise ValueError("legacy question references an unknown page")
        label = raw.get("label")
        prompt_text = str(raw.get("text") or "").strip()
        if not prompt_text:
            raise ValueError("legacy question text must be non-empty")
        raw_id = raw.get("id")
        if raw_id is None:
            generated_task_id, legacy_id = legacy_quarantine_task_identity(
                page_index=page_index,
                label=str(label) if label is not None else None,
                prompt_text=prompt_text,
                parent_task_id=raw.get("parent_task_id"),
                subpart=raw.get("subpart"),
            )
            if generated_task_id in idless_fingerprints:
                raise ValueError("id-less legacy questions require distinct source fingerprints")
            idless_fingerprints.add(generated_task_id)
        else:
            try:
                legacy_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("legacy question id must be an integer") from exc
            generated_task_id = f"legacy-task-{legacy_id}"
        task_id = str(raw.get("task_id") or generated_task_id)
        review_status = _enum_value(ReviewStatus, raw.get("review_status"), ReviewStatus.needs_review)
        task_response_type = _enum_value(ResponseType, raw.get("response_type"), ResponseType.short_text)
        tasks.append(
            DocumentTask(
                id=task_id,
                legacy_question_id=legacy_id,
                order=0,
                label=str(label) if label is not None else None,
                prompt_text=prompt_text,
                anchor_page_index=page_index,
                page_role=_enum_value(PageRole, raw.get("page_role"), PageRole.unknown),
                prompt_block_ids=[],
                evidence_status=EvidenceStatus.legacy_unverified,
                parent_task_id=raw.get("parent_task_id"),
                subpart=raw.get("subpart"),
                response_links=[],
                side_panel_fallback=True,
                response_type=task_response_type,
                confidence=float(raw.get("confidence", raw.get("layout_confidence", 0.0)) or 0.0),
                review_status=review_status,
            )
        )

    tasks.sort(key=lambda task: (task.anchor_page_index, task.legacy_question_id, task.id))
    for order, task in enumerate(tasks):
        task.order = order
    status = ParseStatus.parsed if tasks and all(task.approved for task in tasks) else ParseStatus.low_confidence
    return IntermediateDocument(
        title=title,
        parser=f"{parser}-legacy-adapter",
        status=status,
        document_id=document_id,
        pages=pages,
        blocks=[],
        response_regions=[],
        tasks=tasks,
        warnings=["legacy_flat_manifest_adapter_side_panel_only"],
    )


def migrate_manifest_data(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade old manifests in memory; new writes contain only ``document``."""
    payload = dict(data)
    version = int(payload.get("version") or LEGACY_MANIFEST_VERSION)
    if version > MANIFEST_VERSION:
        raise ValueError(f"unsupported manifest version: {version}")
    warnings = list(payload.get("parse_warnings") or [])
    legacy_questions = payload.pop("questions", None)
    if version >= MANIFEST_VERSION and legacy_questions is not None:
        raise ValueError("canonical manifests cannot contain a parallel questions projection")
    page_count = int(payload.pop("page_count", 1) or 1)
    document = payload.get("document")
    if document is None:
        document = legacy_document_from_questions(
            title=str(payload.get("title") or "Untitled assignment"),
            questions=list(legacy_questions or []),
            page_count=page_count,
            parser=str(payload.get("parser") or "legacy"),
            document_id=str(payload.get("assignment_id") or "") or None,
        ).model_dump(mode="json")
        payload["document"] = document
        if "legacy_flat_manifest_migrated" not in warnings:
            warnings.append("legacy_flat_manifest_migrated")
    if version < MANIFEST_VERSION and "legacy_manifest_v1" not in warnings:
        warnings.append("legacy_manifest_v1")
    payload["version"] = MANIFEST_VERSION
    payload["parse_warnings"] = warnings
    document_parser = (
        payload["document"].get("parser", "legacy")
        if isinstance(payload["document"], dict)
        else getattr(payload["document"], "parser", "legacy")
    )
    payload.setdefault("parser", document_parser)
    payload.setdefault("review_mode", "direct")
    payload.setdefault("review_status", "unreviewed")
    return payload


def build_manifest(
    assignment_id: str,
    title: str,
    questions: list[dict] | None = None,
    parse_status: str = "ok",
    parse_warnings: list[str] | None = None,
    page_count: int = 1,
    ttl_days: int | None = None,
    parser: str = "legacy",
    review_mode: str = "direct",
    review_status: str = "unreviewed",
    document: IntermediateDocument | None = None,
    assignment_capability_hash: str | None = None,
) -> AssignmentManifest:
    expires_at = None
    if ttl_days and ttl_days > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    if document is None:
        document = legacy_document_from_questions(
            title=title,
            questions=questions or [],
            page_count=page_count,
            parser=parser,
            document_id=assignment_id,
        )
    elif document.document_id is None or document.title != title:
        document = document.model_copy(update={"document_id": document.document_id or assignment_id, "title": title})
    return AssignmentManifest(
        assignment_id=assignment_id,
        title=title,
        document=document,
        parse_status=parse_status,
        parse_warnings=parse_warnings or [],
        expires_at=expires_at,
        parser=parser,
        review_mode=review_mode,
        review_status=review_status,
        assignment_capability_hash=assignment_capability_hash,
    )


def canonical_manifest_bytes(manifest: AssignmentManifest) -> bytes:
    """Serialize manifest content deterministically, excluding its MAC tag."""
    payload = manifest.model_dump(mode="json", exclude={"integrity_hmac"})
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _assignment_manifest_tag(
    manifest: AssignmentManifest,
    *,
    expected_assignment_id: str,
    key: bytes,
) -> str:
    if not expected_assignment_id or manifest.assignment_id != expected_assignment_id:
        raise ValueError("manifest assignment_id does not match its storage key")
    if not isinstance(key, bytes) or not key:
        raise ValueError("manifest integrity key is required")
    payload = canonical_manifest_bytes(manifest)
    return hmac.new(
        key,
        _MANIFEST_HMAC_CONTEXT
        + expected_assignment_id.encode("utf-8")
        + b"\0"
        + payload,
        hashlib.sha256,
    ).hexdigest()


def sign_assignment_manifest(
    manifest: AssignmentManifest,
    *,
    expected_assignment_id: str,
    key: bytes,
) -> AssignmentManifest:
    """Return a copy whose complete persisted payload has a server MAC."""
    return manifest.model_copy(
        update={
            "integrity_hmac": _assignment_manifest_tag(
                manifest,
                expected_assignment_id=expected_assignment_id,
                key=key,
            )
        }
    )


def verify_assignment_manifest(
    manifest: AssignmentManifest,
    *,
    expected_assignment_id: str,
    key: bytes,
) -> bool:
    """Verify the stored tag without treating a missing tag as valid."""
    tag = manifest.integrity_hmac
    if not isinstance(tag, str) or len(tag) != 64:
        return False
    try:
        expected = _assignment_manifest_tag(
            manifest,
            expected_assignment_id=expected_assignment_id,
            key=key,
        )
    except ValueError:
        return False
    return hmac.compare_digest(tag, expected)


def parse_manifest_json(raw: str | bytes) -> AssignmentManifest:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return AssignmentManifest.model_validate(migrate_manifest_data(data))
