"""Assignment manifest persistence tests."""
import json
from datetime import datetime, timezone

from manifest import AssignmentManifest, build_manifest, parse_manifest_json


def test_build_manifest_round_trip():
    manifest = build_manifest(
        assignment_id="abc",
        title="Quiz",
        questions=[{"id": 1, "text": "First"}, {"id": 2, "text": "Second"}],
        parse_status="ok",
        parse_warnings=[],
        ttl_days=30,
    )
    raw = manifest.model_dump_json()
    restored = parse_manifest_json(raw)
    assert restored.title == "Quiz"
    assert len(restored.questions) == 2
    assert restored.expires_at is not None


def test_manifest_to_questions_dict():
    manifest = AssignmentManifest(
        assignment_id="x",
        title="T",
        questions=[{"id": 3, "text": "Body"}],
    )
    assert manifest.to_questions_dict() == [{"id": 3, "text": "Body"}]


def test_parse_manifest_json_validates_version():
    payload = {
        "version": 1,
        "assignment_id": "id",
        "title": "T",
        "questions": [{"id": 1, "text": "Q"}],
        "parse_status": "ok",
        "parse_warnings": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "expires_at": None,
    }
    manifest = parse_manifest_json(json.dumps(payload))
    assert manifest.version == 1


def test_manifest_expiration_is_enforced_by_time():
    manifest = AssignmentManifest(
        assignment_id="expired",
        title="T",
        questions=[],
        expires_at="2026-01-01T00:00:00+00:00",
    )
    assert manifest.is_expired(datetime(2026, 1, 2, tzinfo=timezone.utc)) is True


def test_manifest_without_expiration_is_active():
    manifest = AssignmentManifest(assignment_id="active", title="T", questions=[])
    assert manifest.is_expired() is False
