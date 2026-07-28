"""Assignment service unit tests."""
import hashlib

import fitz
import pytest
from fastapi import HTTPException

import assignment_service
import config
from document_model import (
    BlockSemanticRole,
    DocumentBlock,
    DocumentPage,
    DocumentResponseRegion,
    DocumentTask,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ResponseSafety,
    ReviewStatus,
    SourceKind,
    TaskResponseLink,
)
from manifest import build_manifest, parse_manifest_json
from semantic_classifier import NullSemanticClassifier
from tests.conftest import TEST_ASSIGNMENT_ID


def _physical_manifest(pdf_bytes: bytes, *, include_hash: bool = True):
    document = IntermediateDocument(
        title="Bound worksheet",
        parser="test",
        status=ParseStatus.parsed,
        source_sha256=hashlib.sha256(pdf_bytes).hexdigest() if include_hash else None,
        pages=[
            DocumentPage(
                page_index=0,
                width_points=612,
                height_points=792,
                block_ids=["prompt", "response"],
            )
        ],
        blocks=[
            DocumentBlock(
                id="prompt",
                page_index=0,
                reading_order=0,
                text="State the answer.",
                block_label="text",
                bbox=[72, 72, 300, 96],
                confidence=1,
                source=SourceKind.native_pdf,
                semantic_role=BlockSemanticRole.student_prompt,
            ),
            DocumentBlock(
                id="response",
                page_index=0,
                reading_order=1,
                text="",
                block_label="answer_line",
                bbox=[72, 120, 360, 150],
                confidence=1,
                source=SourceKind.pdf_geometry,
                semantic_role=BlockSemanticRole.response_area,
            ),
        ],
        response_regions=[
            DocumentResponseRegion(
                id="response-region",
                page_index=0,
                bbox=[72, 120, 360, 150],
                region_type="answer_line",
                safety=ResponseSafety.approved,
                confidence=1,
                source_block_ids=["response"],
            )
        ],
        tasks=[
            DocumentTask(
                id="task-bound",
                legacy_question_id=1,
                order=0,
                prompt_text="State the answer.",
                anchor_page_index=0,
                prompt_block_ids=["prompt"],
                response_links=[TaskResponseLink(response_region_id="response-region", order=0)],
                side_panel_fallback=False,
                confidence=1,
                review_status=ReviewStatus.approved,
            )
        ],
    )
    return build_manifest(TEST_ASSIGNMENT_ID, "Bound worksheet", document=document)


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


def test_build_export_response_rejects_unrenderable_confirmed_text_without_substitution(monkeypatch):
    source = fitz.open()
    source.new_page()
    pdf_bytes = source.tobytes()
    source.close()
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: ("Worksheet", [{"id": 1, "text": "Prompt", "page": 1, "answer_region": None}]),
    )
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(
            TEST_ASSIGNMENT_ID,
            [{"question_id": 1, "answer_text": "Unsupported \U0001f642"}],
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "UNSUPPORTED_ANSWER_TEXT"


def test_client_manifest_source_binding_rejects_changed_or_unhashed_physical_documents(monkeypatch):
    trusted = fitz.open()
    trusted.new_page(width=612, height=792)
    trusted_bytes = trusted.tobytes()
    trusted.close()
    replacement = fitz.open()
    replacement.new_page(width=612, height=792)
    replacement_bytes = replacement.tobytes()
    replacement.close()

    manifest = _physical_manifest(trusted_bytes)
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: trusted_bytes)
    assert assignment_service.load_assignment_manifest_for_client(TEST_ASSIGNMENT_ID) is manifest
    assert assignment_service.load_assignment_pdf_bytes(TEST_ASSIGNMENT_ID) == trusted_bytes

    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: replacement_bytes)
    with pytest.raises(assignment_service.AssignmentSourceMismatchError):
        assignment_service.load_assignment_manifest_for_client(TEST_ASSIGNMENT_ID)
    with pytest.raises(assignment_service.AssignmentSourceMismatchError):
        assignment_service.load_assignment_pdf_bytes(TEST_ASSIGNMENT_ID)

    unbound_manifest = _physical_manifest(trusted_bytes, include_hash=False)
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: unbound_manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: trusted_bytes)
    with pytest.raises(assignment_service.AssignmentSourceMismatchError):
        assignment_service.load_assignment_manifest_for_client(TEST_ASSIGNMENT_ID)


def test_persisted_canonical_manifest_requires_an_unmodified_server_integrity_tag(monkeypatch):
    source = fitz.open()
    source.new_page(width=612, height=792)
    pdf_bytes = source.tobytes()
    source.close()
    signed = assignment_service._signed_manifest(TEST_ASSIGNMENT_ID, _physical_manifest(pdf_bytes))

    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: signed.model_dump_json(),
    )
    assert assignment_service.load_assignment_manifest(TEST_ASSIGNMENT_ID).integrity_hmac == signed.integrity_hmac

    tampered = signed.model_copy(deep=True)
    tampered.document.pages[0].page_role = PageRole.teacher_guide
    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: tampered.model_dump_json(),
    )
    with pytest.raises(assignment_service.AssignmentManifestIntegrityError):
        assignment_service.load_assignment_manifest(TEST_ASSIGNMENT_ID)

    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: _physical_manifest(pdf_bytes).model_dump_json(),
    )
    with pytest.raises(assignment_service.AssignmentManifestIntegrityError):
        assignment_service.load_assignment_manifest(TEST_ASSIGNMENT_ID)


def test_manifest_integrity_tag_cannot_be_replayed_under_another_assignment_id(monkeypatch):
    source = fitz.open()
    source.new_page(width=612, height=792)
    pdf_bytes = source.tobytes()
    source.close()
    signed = assignment_service._signed_manifest(TEST_ASSIGNMENT_ID, _physical_manifest(pdf_bytes))
    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: signed.model_dump_json(),
    )

    with pytest.raises(assignment_service.AssignmentManifestIntegrityError):
        assignment_service.load_assignment_manifest("another-assignment")


def test_unsigned_legacy_manifest_cannot_rebind_a_capability_or_storage_key(monkeypatch):
    forged_capability = "attacker-known-capability"
    forged = build_manifest(
        TEST_ASSIGNMENT_ID,
        "Legacy",
        questions=[{"id": 1, "text": "State the answer."}],
        assignment_capability_hash=assignment_service.assignment_capability_digest(forged_capability),
    )
    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: forged.model_dump_json(),
    )
    with pytest.raises(assignment_service.AssignmentManifestIntegrityError):
        assignment_service.load_assignment_manifest(TEST_ASSIGNMENT_ID)
    with pytest.raises(assignment_service.AssignmentManifestIntegrityError):
        assignment_service.require_assignment_capability(TEST_ASSIGNMENT_ID, forged_capability)

    cross_assignment = build_manifest(
        "attacker-assignment",
        "Legacy",
        questions=[{"id": 1, "text": "State the answer."}],
    )
    monkeypatch.setattr(
        assignment_service,
        "download_manifest_from_gcs",
        lambda _id: cross_assignment.model_dump_json(),
    )
    with pytest.raises(assignment_service.AssignmentManifestIntegrityError):
        assignment_service.load_assignment_manifest(TEST_ASSIGNMENT_ID)


def test_review_persists_a_fresh_manifest_integrity_tag(monkeypatch):
    source = fitz.open()
    source.new_page(width=612, height=792)
    pdf_bytes = source.tobytes()
    source.close()
    manifest = _physical_manifest(pdf_bytes).model_copy(update={"review_mode": "teacher"})
    uploaded = {}
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)
    monkeypatch.setattr(
        assignment_service,
        "upload_manifest_to_gcs",
        lambda _id, raw: uploaded.setdefault("raw", raw),
    )

    updated = assignment_service.review_assignment(TEST_ASSIGNMENT_ID, [])
    assert updated.integrity_hmac
    restored = parse_manifest_json(uploaded["raw"])
    assert assignment_service._verify_loaded_manifest(TEST_ASSIGNMENT_ID, restored) is restored


def test_client_manifest_binding_rejects_unrecorded_pdf_display_transforms(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=612, height=792)
    page.set_rotation(90)
    pdf_bytes = source.tobytes()
    source.close()
    manifest = _physical_manifest(pdf_bytes)
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)

    with pytest.raises(assignment_service.AssignmentSourceMismatchError):
        assignment_service.load_assignment_manifest_for_client(TEST_ASSIGNMENT_ID)
    with pytest.raises(assignment_service.AssignmentSourceMismatchError):
        assignment_service.load_assignment_pdf_bytes(TEST_ASSIGNMENT_ID)


def test_client_manifest_binding_uses_user_unit_scaled_extraction_bounds(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=612, height=792)
    source.xref_set_key(page.xref, "UserUnit", "2")
    pdf_bytes = source.tobytes()
    source.close()
    payload = _physical_manifest(pdf_bytes).document.model_dump(mode="json")
    payload["pages"][0].update(
        {
            "width_points": 1224,
            "height_points": 1584,
            "display_transform_required": True,
        }
    )
    payload["response_regions"][0]["safety"] = "unsafe"
    payload["tasks"][0].update(
        {"side_panel_fallback": True, "review_status": "needs_review"}
    )
    manifest = build_manifest(
        TEST_ASSIGNMENT_ID,
        "Bound worksheet",
        document=IntermediateDocument.model_validate(payload),
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)

    assert assignment_service.load_assignment_manifest_for_client(TEST_ASSIGNMENT_ID) is manifest


def test_client_manifest_source_binding_leaves_legacy_side_panel_documents_download_free(monkeypatch):
    legacy = build_manifest(
        TEST_ASSIGNMENT_ID,
        "Legacy",
        questions=[{"id": 1, "text": "State the answer."}],
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: legacy)
    monkeypatch.setattr(
        assignment_service,
        "_download_pdf_bytes",
        lambda _id: (_ for _ in ()).throw(AssertionError("legacy document should not fetch a PDF")),
    )

    assert assignment_service.load_assignment_manifest_for_client(TEST_ASSIGNMENT_ID) is legacy


def test_teacher_review_cannot_approve_a_response_target_against_a_changed_pdf(monkeypatch):
    trusted = fitz.open()
    trusted.new_page(width=612, height=792)
    trusted_bytes = trusted.tobytes()
    trusted.close()
    replacement = fitz.open()
    replacement.new_page(width=612, height=792)
    replacement_bytes = replacement.tobytes()
    replacement.close()
    manifest = _physical_manifest(trusted_bytes).model_copy(update={"review_mode": "teacher"})
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: replacement_bytes)

    with pytest.raises(assignment_service.AssignmentSourceMismatchError):
        assignment_service.review_assignment(TEST_ASSIGNMENT_ID, [])


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
    monkeypatch.setattr(config, "PDF_PARSER_MODE", "legacy")

    pdf_bytes = tmp_pdf_question_format.read_bytes()
    manifest = assignment_service.persist_assignment_from_pdf_bytes("abc-123", pdf_bytes)
    assert manifest.parse_status == "layout_review_required"
    assert manifest.integrity_hmac
    assert uploaded["pdf"] == pdf_bytes
    restored = parse_manifest_json(uploaded["manifest"])
    assert restored.title == manifest.title
    assert assignment_service._verify_loaded_manifest("abc-123", restored) is restored
    assert len(restored.questions) >= 2
    assert restored.page_count >= 1


def test_load_assignment_manifest_backfill(monkeypatch, tmp_pdf_question_format):
    pdf_bytes = tmp_pdf_question_format.read_bytes()
    manifest_json = None

    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)
    monkeypatch.setattr(assignment_service, "download_manifest_from_gcs", lambda _id: None)
    monkeypatch.setattr(config, "PDF_PARSER_MODE", "legacy")

    def capture_manifest(assignment_id, raw):
        nonlocal manifest_json
        manifest_json = raw

    monkeypatch.setattr(assignment_service, "upload_manifest_to_gcs", capture_manifest)

    title, questions = assignment_service.load_assignment_from_gcs("legacy-id")
    assert title
    assert questions
    # Stage 11: capability-less signed manifests must not be persisted.
    assert manifest_json is None


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
    monkeypatch.setattr(config, "DOCUMENT_SEMANTIC_PROVIDER", "gemini")
    monkeypatch.setattr(assignment_service, "GeminiSemanticClassifier", _FakeGeminiClassifier)
    monkeypatch.setattr(assignment_service, "parse_document", fake_parse)

    assignment_service._parse_and_build_manifest("candidate", str(tmp_pdf_question_format))
    assert isinstance(captured[-1], NullSemanticClassifier)

    monkeypatch.setattr(config, "ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS", True)
    assignment_service._parse_and_build_manifest("candidate", str(tmp_pdf_question_format))
    assert isinstance(captured[-1], _FakeGeminiClassifier)

    monkeypatch.setattr(config, "DOCUMENT_SEMANTIC_PROVIDER", "none")
    assignment_service._parse_and_build_manifest("candidate", str(tmp_pdf_question_format))
    assert isinstance(captured[-1], NullSemanticClassifier)
