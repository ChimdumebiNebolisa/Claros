"""Assignment manifest schema and helpers for parse-once worksheet ingestion.

Coordinate system (manifest v2):
  PDF points with origin at the top-left of each page (PyMuPDF page space).
  Rectangles are [x0, y0, x1, y1] where x0 < x1 and y0 < y1.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MANIFEST_VERSION = 2
LEGACY_MANIFEST_VERSION = 1
CANONICAL_MANIFEST_NAME = "manifest.json"

LayoutConfidence = Literal["high", "medium", "low", "manual"]

MIN_ANSWER_WIDTH = 24.0
MIN_ANSWER_HEIGHT = 18.0


class ManifestPage(BaseModel):
    page_index: int = Field(ge=0)
    width_points: float = Field(gt=0)
    height_points: float = Field(gt=0)
    has_usable_text: bool = True
    requires_ocr: bool = False

    @field_validator("width_points", "height_points", mode="before")
    @classmethod
    def _finite_positive(cls, value: Any) -> float:
        number = _require_finite_number(value, "page dimension")
        if number <= 0:
            raise ValueError("page dimensions must be positive")
        return float(number)


class ManifestQuestion(BaseModel):
    id: int
    text: str
    page_index: int | None = None
    question_bbox: list[float] | None = None
    answer_bbox: list[float] | None = None
    layout_confidence: LayoutConfidence | None = None
    layout_warnings: list[str] = Field(default_factory=list)

    @field_validator("question_bbox", "answer_bbox", mode="before")
    @classmethod
    def _optional_bbox(cls, value: Any) -> list[float] | None:
        if value is None:
            return None
        return normalize_bbox(value)


class AssignmentManifest(BaseModel):
    version: int = MANIFEST_VERSION
    assignment_id: str
    title: str
    questions: list[ManifestQuestion]
    pages: list[ManifestPage] = Field(default_factory=list)
    parse_status: str = "ok"  # ok | fallback_single_block | empty_extraction | requires_ocr
    parse_warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None

    def to_questions_dict(self) -> list[dict]:
        """Return questions for API consumers. Always includes id/text; layout fields when present."""
        result: list[dict] = []
        for q in self.questions:
            item: dict[str, Any] = {"id": q.id, "text": q.text}
            if q.page_index is not None:
                item["page_index"] = q.page_index
            if q.question_bbox is not None:
                item["question_bbox"] = list(q.question_bbox)
            if q.answer_bbox is not None:
                item["answer_bbox"] = list(q.answer_bbox)
            if q.layout_confidence is not None:
                item["layout_confidence"] = q.layout_confidence
            if q.layout_warnings:
                item["layout_warnings"] = list(q.layout_warnings)
            result.append(item)
        return result

    def to_pages_dict(self) -> list[dict]:
        return [p.model_dump() for p in self.pages]

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

    def page_for_index(self, page_index: int) -> ManifestPage | None:
        for page in self.pages:
            if page.page_index == page_index:
                return page
        return None


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
    """Upgrade v1 (or partial) manifests in memory without mutating stored bytes."""
    payload = dict(data)
    version = int(payload.get("version") or LEGACY_MANIFEST_VERSION)
    warnings = list(payload.get("parse_warnings") or [])
    if version < MANIFEST_VERSION:
        if "legacy_manifest_v1" not in warnings:
            warnings.append("legacy_manifest_v1")
        if "missing_layout_regions" not in warnings:
            warnings.append("missing_layout_regions")
        payload["version"] = MANIFEST_VERSION
    payload["parse_warnings"] = warnings
    payload.setdefault("pages", [])
    migrated_questions = []
    for question in payload.get("questions") or []:
        q = dict(question)
        q.setdefault("layout_warnings", [])
        if q.get("page_index") is None and "legacy_missing_regions" not in q["layout_warnings"]:
            q["layout_warnings"] = list(q["layout_warnings"]) + ["legacy_missing_regions"]
        migrated_questions.append(q)
    payload["questions"] = migrated_questions
    return payload


def build_manifest(
    assignment_id: str,
    title: str,
    questions: list[dict],
    parse_status: str = "ok",
    parse_warnings: list[str] | None = None,
    ttl_days: int | None = None,
    pages: list[dict] | None = None,
) -> AssignmentManifest:
    expires_at = None
    if ttl_days and ttl_days > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    return AssignmentManifest(
        version=MANIFEST_VERSION,
        assignment_id=assignment_id,
        title=title,
        questions=[ManifestQuestion.model_validate(q) for q in questions],
        pages=[ManifestPage.model_validate(p) for p in (pages or [])],
        parse_status=parse_status,
        parse_warnings=parse_warnings or [],
        expires_at=expires_at,
    )


def parse_manifest_json(raw: str | bytes) -> AssignmentManifest:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return AssignmentManifest.model_validate(migrate_manifest_data(data))
