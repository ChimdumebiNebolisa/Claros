"""Assignment service unit tests."""
import pytest
from fastapi import HTTPException

import assignment_service
import config
from manifest import parse_manifest_json
from tests.conftest import TEST_ASSIGNMENT_ID


def test_export_filename_strips_unsafe_characters():
    assert assignment_service._export_filename("550e8400-e29b-41d4-a716-446655440000") == (
        "claros-550e8400-e29b-41d4-a716-446655440000.pdf"
    )
    assert assignment_service._export_filename('..\\..\\550e8400-e29b-41d4-a716-446655440000') == (
        "claros-550e8400-e29b-41d4-a716-446655440000.pdf"
    )


def test_format_assignment_text_joins_questions():
    text = assignment_service.format_assignment_text(
        "Quiz",
        [{"id": 1, "text": "First?"}, {"id": 2, "text": "Second?"}],
    )
    assert "Quiz" in text
    assert "Question 1: First?" in text
    assert "Question 2: Second?" in text


def test_build_export_response_maps_value_error_to_404(monkeypatch):
    def raise_missing(_assignment_id: str):
        raise ValueError("missing")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_missing)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(TEST_ASSIGNMENT_ID, [])
    assert exc.value.status_code == 404


def test_build_export_response_maps_backend_error_to_500(monkeypatch):
    def raise_backend(_assignment_id: str):
        raise RuntimeError("gcs down")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_backend)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(TEST_ASSIGNMENT_ID, [])
    assert exc.value.status_code == 500


def test_persist_assignment_writes_manifest(monkeypatch, tmp_pdf_question_format):
    uploaded = {}

    def fake_upload_pdf(assignment_id, pdf_bytes):
        uploaded["pdf"] = pdf_bytes

    def fake_upload_manifest(assignment_id, manifest_json):
        uploaded["manifest"] = manifest_json

    monkeypatch.setattr(assignment_service, "upload_pdf_to_gcs", fake_upload_pdf)
    monkeypatch.setattr(assignment_service, "upload_manifest_to_gcs", fake_upload_manifest)
    monkeypatch.setattr(config, "ASSIGNMENT_TTL_DAYS", 30)

    pdf_bytes = tmp_pdf_question_format.read_bytes()
    manifest = assignment_service.persist_assignment_from_pdf_bytes("abc-123", pdf_bytes)
    assert manifest.parse_status == "ok"
    assert uploaded["pdf"] == pdf_bytes
    restored = parse_manifest_json(uploaded["manifest"])
    assert restored.title == manifest.title
    assert len(restored.questions) >= 2


def test_load_assignment_manifest_backfill(monkeypatch, tmp_pdf_question_format):
    pdf_bytes = tmp_pdf_question_format.read_bytes()
    manifest_json = None

    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)
    monkeypatch.setattr(assignment_service, "download_manifest_from_gcs", lambda _id: None)

    def capture_manifest(assignment_id, raw):
        nonlocal manifest_json
        manifest_json = raw

    monkeypatch.setattr(assignment_service, "upload_manifest_to_gcs", capture_manifest)

    title, questions = assignment_service.load_assignment_from_gcs("legacy-id")
    assert title
    assert questions
    assert manifest_json is not None


def test_expired_manifest_is_rejected(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: b'{"version":1,"assignment_id":"expired","title":"T","questions":[],"expires_at":"2020-01-01T00:00:00+00:00"}',
    )
    with pytest.raises(assignment_service.AssignmentExpiredError):
        assignment_service.load_assignment_manifest("expired")
