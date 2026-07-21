"""Assignment service unit tests."""
import pytest
from fastapi import HTTPException

import assignment_service
import config
from document_model import DocumentPage, IntermediateDocument, ParseStatus
from manifest import build_manifest, parse_manifest_json
from semantic_classifier import NullSemanticClassifier
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

    monkeypatch.setattr(assignment_service, "load_assignment_manifest", raise_missing)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(TEST_ASSIGNMENT_ID, [])
    assert exc.value.status_code == 404


def test_build_export_response_maps_backend_error_to_500(monkeypatch):
    def raise_backend(_assignment_id: str):
        raise RuntimeError("gcs down")

    monkeypatch.setattr(assignment_service, "load_assignment_manifest", raise_backend)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(TEST_ASSIGNMENT_ID, [])
    assert exc.value.status_code == 500


def test_build_export_response_original_pdf_path(monkeypatch, tmp_path):
    from tests.layout_fixtures import write_simple_one_column
    from parser import parse_pdf_with_diagnostics

    path = write_simple_one_column(tmp_path / "layout_export.pdf")
    title, questions, warnings, status = parse_pdf_with_diagnostics(path)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=title,
        questions=[
            {
                "id": q.id,
                "text": q.text,
                "page": q.page,
                "answer_region": q.answer_region,
                "detected_answer_region": q.detected_answer_region,
                "layout_confidence": q.layout_confidence,
                "needs_layout_review": q.needs_layout_review,
            }
            for q in questions
        ],
        parse_status=status,
        parse_warnings=warnings,
        page_count=1,
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: path.read_bytes())

    response = assignment_service.build_export_response(
        TEST_ASSIGNMENT_ID,
        [{"question_id": 1, "answer_text": "x = 5", "answer_region": questions[0].answer_region}],
    )
    assert response.status_code == 200
    assert response.body.startswith(b"%PDF")


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
    assert manifest.parse_status == "layout_review_required"
    assert uploaded["pdf"] == pdf_bytes
    restored = parse_manifest_json(uploaded["manifest"])
    assert restored.title == manifest.title
    assert len(restored.questions) >= 2
    assert restored.page_count >= 1


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


def test_hybrid_semantics_cannot_run_on_upload_without_explicit_worker_gate(
    monkeypatch,
    tmp_pdf_question_format,
):
    captured = []

    class _FakeGeminiClassifier:
        pass

    def fake_parse(_pdf_bytes, *, semantic_classifier, **_kwargs):
        captured.append(semantic_classifier)
        return IntermediateDocument(
            title="Candidate",
            parser="hybrid-ppstructurev3-gemini",
            status=ParseStatus.low_confidence,
            pages=[DocumentPage(page_index=0, width_points=612, height_points=792)],
            blocks=[],
            tasks=[],
        )

    monkeypatch.setattr(config, "PDF_PARSER_MODE", "hybrid")
    monkeypatch.setattr(config, "ENABLE_DOCUMENT_SEMANTICS", True)
    monkeypatch.setattr(config, "ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS", False)
    monkeypatch.setattr(assignment_service, "GeminiSemanticClassifier", _FakeGeminiClassifier)
    monkeypatch.setattr(assignment_service, "parse_document", fake_parse)

    assignment_service._parse_and_build_manifest("candidate", str(tmp_pdf_question_format))
    assert isinstance(captured[-1], NullSemanticClassifier)

    monkeypatch.setattr(config, "ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS", True)
    assignment_service._parse_and_build_manifest("candidate", str(tmp_pdf_question_format))
    assert isinstance(captured[-1], _FakeGeminiClassifier)
