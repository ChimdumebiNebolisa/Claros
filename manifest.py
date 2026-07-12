"""Assignment manifest schema and helpers for parse-once worksheet ingestion."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

MANIFEST_VERSION = 1
CANONICAL_MANIFEST_NAME = "manifest.json"


class ManifestQuestion(BaseModel):
    id: int
    text: str


class AssignmentManifest(BaseModel):
    version: int = MANIFEST_VERSION
    assignment_id: str
    title: str
    questions: list[ManifestQuestion]
    parse_status: str = "ok"  # ok | fallback_single_block | empty_extraction
    parse_warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None

    def to_questions_dict(self) -> list[dict]:
        return [{"id": q.id, "text": q.text} for q in self.questions]

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


def build_manifest(
    assignment_id: str,
    title: str,
    questions: list[dict],
    parse_status: str = "ok",
    parse_warnings: list[str] | None = None,
    ttl_days: int | None = None,
) -> AssignmentManifest:
    expires_at = None
    if ttl_days and ttl_days > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    return AssignmentManifest(
        assignment_id=assignment_id,
        title=title,
        questions=[ManifestQuestion(id=q["id"], text=q["text"]) for q in questions],
        parse_status=parse_status,
        parse_warnings=parse_warnings or [],
        expires_at=expires_at,
    )


def parse_manifest_json(raw: str | bytes) -> AssignmentManifest:
    data = json.loads(raw)
    return AssignmentManifest.model_validate(data)
