"""Assignment manifest schema and helpers for parse-once worksheet ingestion."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from document_model import IntermediateDocument

MANIFEST_VERSION = 3
LEGACY_MANIFEST_VERSION = 1
CANONICAL_MANIFEST_NAME = "manifest.json"

LayoutConfidence = Literal["high", "medium", "low", "manual"]

MIN_ANSWER_WIDTH = 24.0
MIN_ANSWER_HEIGHT = 18.0


class ManifestQuestion(BaseModel):
    id: int
    task_id: str | None = None
    text: str
    label: str | None = None
    page: int = 1
    page_index: int | None = None
    page_role: str = "unknown"
    prompt_region: dict[str, float] | None = None
    answer_region: dict[str, float] | None = None
    detected_answer_region: dict[str, float] | None = None
    prompt_bbox: list[float] | None = None
    answer_bbox: list[float] | None = None
    response_type: str = "short_text"
    confidence: float = 0.0
    layout_confidence: float = 0.0
    needs_layout_review: bool = True
    review_status: str = "needs_review"
    answer_region_status: str = "missing"
    source_blocks: list[str] = Field(default_factory=list)
    approved: bool = False


class AssignmentManifest(BaseModel):
    version: int = MANIFEST_VERSION
    assignment_id: str
    title: str
    questions: list[ManifestQuestion]
    page_count: int = 1
    parse_status: str = "ok"  # ok | layout_review_required | unsupported_layout | requires_ocr
    parse_warnings: list[str] = Field(default_factory=list)
    parser: str = "legacy"
    review_mode: str = "direct"
    review_status: str = "unreviewed"
    document: IntermediateDocument | None = None
    assignment_capability_hash: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None

    def to_questions_dict(self, *, approved_only: bool = False) -> list[dict]:
        return [
            {
                "id": q.id,
                "task_id": q.task_id,
                "label": q.label,
                "text": q.text,
                "page": q.page,
                "page_index": q.page_index if q.page_index is not None else q.page - 1,
                "page_role": q.page_role,
                "prompt_region": q.prompt_region,
                "answer_region": q.answer_region,
                "detected_answer_region": q.detected_answer_region,
                "prompt_bbox": q.prompt_bbox,
                "answer_bbox": q.answer_bbox,
                "response_type": q.response_type,
                "confidence": q.confidence,
                "layout_confidence": q.layout_confidence,
                "needs_layout_review": q.needs_layout_review,
                "review_status": q.review_status,
                "answer_region_status": q.answer_region_status,
                "source_blocks": q.source_blocks,
                "approved": q.approved,
            }
            for q in self.questions
            if not approved_only or q.approved
        ]

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return expires <= (now or datetime.now(timezone.utc))

    def model_dump_json(self, **kwargs: Any) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)


def _require_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def normalize_bbox(raw: Any) -> list[float]:
    """Normalize a rectangle to [x0, y0, x1, y1] with finite numbers and positive size."""
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


def migrate_manifest_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize older manifests in memory without mutating stored bytes."""
    payload = dict(data)
    version = int(payload.get("version") or LEGACY_MANIFEST_VERSION)
    warnings = list(payload.get("parse_warnings") or [])
    if version < MANIFEST_VERSION:
        if "legacy_manifest_v1" not in warnings:
            warnings.append("legacy_manifest_v1")
        payload["version"] = MANIFEST_VERSION
    questions = []
    for raw_question in payload.get("questions") or []:
        question = dict(raw_question)
        approved = bool(
            question.get("approved", not question.get("needs_layout_review", True) and question.get("answer_region"))
        )
        question.setdefault("page_index", max(0, int(question.get("page", 1)) - 1))
        question.setdefault("approved", approved)
        question.setdefault("review_status", "auto_approved" if approved else "needs_review")
        question.setdefault(
            "answer_region_status",
            "detected" if question.get("answer_region") else "missing",
        )
        questions.append(question)
    payload["questions"] = questions
    payload.setdefault("page_count", 1)
    payload.setdefault("parser", "legacy")
    payload.setdefault("review_mode", "direct")
    payload.setdefault("review_status", "unreviewed")
    payload["parse_warnings"] = warnings
    return payload


def build_manifest(
    assignment_id: str,
    title: str,
    questions: list[dict],
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
    return AssignmentManifest(
        assignment_id=assignment_id,
        title=title,
        questions=[ManifestQuestion.model_validate(q) for q in questions],
        page_count=page_count,
        parse_status=parse_status,
        parse_warnings=parse_warnings or [],
        expires_at=expires_at,
        parser=parser,
        review_mode=review_mode,
        review_status=review_status,
        document=document,
        assignment_capability_hash=assignment_capability_hash,
    )


def parse_manifest_json(raw: str | bytes) -> AssignmentManifest:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return AssignmentManifest.model_validate(migrate_manifest_data(data))
