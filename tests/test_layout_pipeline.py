"""Worksheet layout, preview, and original-PDF export coverage."""
from __future__ import annotations

import json

import fitz
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import assignment_service
import config
import main as main_module
from exporter import LayoutExportError, build_layout_export_pdf
from manifest import MANIFEST_VERSION, build_manifest, parse_manifest_json, validate_bbox_within_page
from parser import parse_pdf_layout
from schemas import validate_layout_overrides
from tests.conftest import TEST_ASSIGNMENT_ID
from tests.layout_fixtures import (
    write_ambiguous_spacing,
    write_answer_lines,
    write_image_only,
    write_multiline_questions,
    write_multipage,
    write_simple_one_column,
    write_table_like,
    write_two_column,
    write_unicode_math,
)

client = TestClient(main_module.app)


def _within(a: float, b: float, tol: float = 12.0) -> bool:
    return abs(a - b) <= tol


def test_manifest_v2_round_trip_includes_pages_and_regions():
    manifest = build_manifest(
        assignment_id="abc",
        title="Quiz",
        questions=[
            {
                "id": 1,
                "text": "Solve for x",
                "page_index": 0,
                "question_bbox": [72, 120, 540, 178],
                "answer_bbox": [72, 188, 540, 250],
                "layout_confidence": "high",
                "layout_warnings": [],
            }
        ],
        pages=[
            {
                "page_index": 0,
                "width_points": 612,
                "height_points": 792,
                "has_usable_text": True,
                "requires_ocr": False,
            }
        ],
    )
    restored = parse_manifest_json(manifest.model_dump_json())
    assert restored.version == MANIFEST_VERSION
    assert restored.pages[0].width_points == 612
    assert restored.questions[0].answer_bbox == [72, 188, 540, 250]
    payload = restored.to_questions_dict()
    assert payload[0]["answer_bbox"] == [72, 188, 540, 250]


def test_legacy_manifest_v1_migrates_in_memory_with_warning():
    raw = json.dumps(
        {
            "version": 1,
            "assignment_id": "legacy",
            "title": "Old",
            "questions": [{"id": 1, "text": "Q"}],
            "parse_status": "ok",
            "parse_warnings": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": None,
        }
    )
    manifest = parse_manifest_json(raw)
    assert manifest.version == MANIFEST_VERSION
    assert "legacy_manifest_v1" in manifest.parse_warnings
    assert "missing_layout_regions" in manifest.parse_warnings
    assert "legacy_missing_regions" in manifest.questions[0].layout_warnings


def test_validate_bbox_rejects_nan_and_outside_page():
    with pytest.raises(ValueError):
        validate_bbox_within_page([0, 0, float("nan"), 10], page_width=100, page_height=100)
    with pytest.raises(ValueError):
        validate_bbox_within_page([0, 0, 200, 50], page_width=100, page_height=100)


def test_simple_one_column_layout(tmp_path):
    path = write_simple_one_column(tmp_path / "simple.pdf")
    result = parse_pdf_layout(path)
    assert result.parse_status == "ok"
    assert len(result.pages) == 1
    assert result.pages[0]["requires_ocr"] is False
    assert [q.id for q in result.questions] == [1, 2]
    for q in result.questions:
        assert q.page_index == 0
        assert q.question_bbox is not None
        assert q.answer_bbox is not None
        assert q.layout_confidence in {"high", "medium"}


def test_multiline_question_keeps_continuation(tmp_path):
    path = write_multiline_questions(tmp_path / "multi.pdf")
    result = parse_pdf_layout(path)
    q1 = next(q for q in result.questions if q.id == 1)
    assert "continuation" in q1.text.lower()
    assert q1.answer_bbox is not None


def test_two_column_does_not_merge_columns(tmp_path):
    path = write_two_column(tmp_path / "two_col.pdf")
    result = parse_pdf_layout(path)
    ids = [q.id for q in result.questions]
    assert ids == [1, 2, 3, 4]
    left = [q for q in result.questions if q.id in (1, 2)]
    right = [q for q in result.questions if q.id in (3, 4)]
    assert all(q.question_bbox[0] < 200 for q in left)
    assert all(q.question_bbox[0] > 250 for q in right)
    # Left question text must not include right-column prompts
    assert "Right column" not in left[0].text
    # Same-column successor must preserve answer regions for every item
    assert all(q.answer_bbox is not None for q in result.questions)


def test_fallback_export_uses_reconstructed_pdf(monkeypatch, tmp_pdf_no_questions):
    """Pages without usable answer regions must use ReportLab, not a blank original."""
    from parser import parse_pdf_layout

    result = parse_pdf_layout(tmp_pdf_no_questions)
    assert result.parse_status == "fallback_single_block"
    assert all(q.answer_bbox is None for q in result.questions)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=result.title,
        questions=[
            {
                "id": q.id,
                "text": q.text,
                "page_index": q.page_index,
                "question_bbox": q.question_bbox,
                "answer_bbox": q.answer_bbox,
                "layout_confidence": q.layout_confidence,
                "layout_warnings": q.layout_warnings or [],
            }
            for q in result.questions
        ],
        pages=result.pages,
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    # Layout download must not be required for reconstructed fallback.
    monkeypatch.setattr(
        assignment_service,
        "_download_pdf_bytes",
        lambda _id: (_ for _ in ()).throw(AssertionError("should not download original")),
    )
    response = assignment_service.build_export_response(
        TEST_ASSIGNMENT_ID,
        [{"question_id": 0, "answer_text": "student answer"}],
    )
    assert response.status_code == 200
    doc = fitz.open(stream=response.body, filetype="pdf")
    try:
        text = " ".join(page.get_text() for page in doc)
        assert "student answer" in text
        assert "Claros - Assignment Answers" in text
    finally:
        doc.close()


def test_layout_override_outside_page_returns_422(monkeypatch, tmp_path):
    path = write_simple_one_column(tmp_path / "override_oob.pdf")
    result = parse_pdf_layout(path)
    q1 = next(q for q in result.questions if q.id == 1)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=result.title,
        questions=[
            {
                "id": q1.id,
                "text": q1.text,
                "page_index": q1.page_index,
                "question_bbox": q1.question_bbox,
                "answer_bbox": q1.answer_bbox,
                "layout_confidence": q1.layout_confidence,
                "layout_warnings": [],
            }
        ],
        pages=result.pages,
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: path.read_bytes())
    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(
            TEST_ASSIGNMENT_ID,
            [{"question_id": 1, "answer_text": "x = 5"}],
            layout_overrides=[
                {
                    "question_id": 1,
                    "page_index": 0,
                    "answer_bbox": [0, 0, 900, 50],
                }
            ],
        )
    assert exc.value.status_code == 422


def test_table_like_numbered_items(tmp_path):
    path = write_table_like(tmp_path / "table.pdf")
    result = parse_pdf_layout(path)
    assert [q.id for q in result.questions] == [1, 2]
    assert result.questions[0].answer_bbox is not None


def test_multipage_page_indexes(tmp_path):
    path = write_multipage(tmp_path / "multi_page.pdf")
    result = parse_pdf_layout(path)
    assert len(result.pages) == 2
    by_id = {q.id: q for q in result.questions}
    assert by_id[1].page_index == 0
    assert by_id[2].page_index == 1


def test_unicode_math_normalized(tmp_path):
    path = write_unicode_math(tmp_path / "unicode.pdf")
    result = parse_pdf_layout(path)
    assert "\u2212" not in result.questions[0].text
    assert "Solve x" in result.questions[0].text


def test_answer_lines_fixture_detects_regions(tmp_path):
    path = write_answer_lines(tmp_path / "lines.pdf")
    result = parse_pdf_layout(path)
    assert all(q.answer_bbox for q in result.questions)


def test_image_only_requires_ocr_without_fake_question(tmp_path):
    path = write_image_only(tmp_path / "scan.pdf")
    result = parse_pdf_layout(path)
    assert result.parse_status == "requires_ocr"
    assert result.questions == []
    assert result.pages[0]["requires_ocr"] is True
    assert "requires_ocr" in result.warnings


def test_ambiguous_spacing_marks_low_or_missing_region(tmp_path):
    path = write_ambiguous_spacing(tmp_path / "ambiguous.pdf")
    result = parse_pdf_layout(path)
    assert len(result.questions) >= 2
    assert any(
        q.layout_confidence in {"low", "medium"} or q.answer_bbox is None
        for q in result.questions
    )


def test_layout_export_preserves_original_pages_and_places_answer(tmp_path):
    path = write_simple_one_column(tmp_path / "export_src.pdf")
    result = parse_pdf_layout(path)
    original = path.read_bytes()
    q1 = next(q for q in result.questions if q.id == 1)
    out = build_layout_export_pdf(
        original,
        [
            {
                "id": q.id,
                "text": q.text,
                "page_index": q.page_index,
                "answer_bbox": q.answer_bbox,
            }
            for q in result.questions
        ],
        [{"question_id": 1, "answer_text": "x = 5"}],
        pages=result.pages,
    )
    doc = fitz.open(stream=out, filetype="pdf")
    try:
        assert doc.page_count == 1
        assert _within(doc[0].rect.width, 612)
        assert _within(doc[0].rect.height, 792)
        text = doc[0].get_text()
        assert "Algebra Practice" in text
        assert "x = 5" in text
        assert "Question 1" in text
    finally:
        doc.close()


def test_layout_export_multiline_answer(tmp_path):
    path = write_simple_one_column(tmp_path / "export_multi.pdf")
    result = parse_pdf_layout(path)
    q1 = next(q for q in result.questions if q.id == 1)
    out = build_layout_export_pdf(
        path.read_bytes(),
        [{"id": 1, "text": q1.text, "page_index": 0, "answer_bbox": q1.answer_bbox}],
        [{"question_id": 1, "answer_text": "line one\nline two"}],
        pages=result.pages,
    )
    doc = fitz.open(stream=out, filetype="pdf")
    try:
        text = doc[0].get_text()
        assert "line one" in text
        assert "line two" in text
    finally:
        doc.close()


def test_layout_export_overflow_lists_question(tmp_path):
    path = write_simple_one_column(tmp_path / "overflow.pdf")
    result = parse_pdf_layout(path)
    tiny = [72, 150, 120, 168]
    with pytest.raises(LayoutExportError) as exc:
        build_layout_export_pdf(
            path.read_bytes(),
            [{"id": 1, "text": "q", "page_index": 0, "answer_bbox": tiny}],
            [{"question_id": 1, "answer_text": "x = " + ("5" * 400)}],
            pages=result.pages,
        )
    assert 1 in exc.value.question_ids


def test_layout_export_unresolved_without_override_errors(tmp_path):
    path = write_simple_one_column(tmp_path / "unresolved.pdf")
    result = parse_pdf_layout(path)
    with pytest.raises(LayoutExportError):
        build_layout_export_pdf(
            path.read_bytes(),
            [{"id": 1, "text": "q", "page_index": 0, "answer_bbox": None}],
            [{"question_id": 1, "answer_text": "answer"}],
            pages=result.pages,
        )


def test_invalid_override_outside_page_rejected_by_schema():
    with pytest.raises(Exception):
        validate_layout_overrides(
            [{"question_id": 1, "page_index": 0, "answer_bbox": [0, 0, -10, 20]}]
        )


def test_preview_route_happy_path(monkeypatch, tmp_path):
    path = write_simple_one_column(tmp_path / "preview.pdf")
    pdf_bytes = path.read_bytes()
    result = parse_pdf_layout(path)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=result.title,
        questions=[
            {
                "id": q.id,
                "text": q.text,
                "page_index": q.page_index,
                "question_bbox": q.question_bbox,
                "answer_bbox": q.answer_bbox,
                "layout_confidence": q.layout_confidence,
                "layout_warnings": q.layout_warnings or [],
            }
            for q in result.questions
        ],
        pages=result.pages,
    )

    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/0/preview")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert "private" in response.headers.get("cache-control", "")


def test_preview_rejects_invalid_page(monkeypatch, tmp_path):
    path = write_simple_one_column(tmp_path / "preview2.pdf")
    result = parse_pdf_layout(path)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=result.title,
        questions=[],
        pages=result.pages,
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: path.read_bytes())
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/9/preview")
    assert response.status_code == 404


def test_preview_rejects_expired(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_manifest",
        lambda _id: (_ for _ in ()).throw(assignment_service.AssignmentExpiredError("expired")),
    )
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/0/preview")
    assert response.status_code == 410


def test_preview_rejects_huge_dpi_budget(monkeypatch, tmp_path):
    path = write_simple_one_column(tmp_path / "huge.pdf")
    result = parse_pdf_layout(path)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=result.title,
        questions=[],
        pages=[
            {
                "page_index": 0,
                "width_points": 5000,
                "height_points": 5000,
                "has_usable_text": True,
                "requires_ocr": False,
            }
        ],
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: path.read_bytes())
    # Patch downloaded page size by using a huge synthetic PDF
    big = fitz.open()
    big.new_page(width=5000, height=5000)
    blob = big.tobytes()
    big.close()
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: blob)
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/0/preview?dpi=200")
    assert response.status_code == 400


def test_ocr_adapter_null_boundary():
    from ocr_adapter import get_ocr_adapter

    result = get_ocr_adapter().extract_page_text(b"%PDF", 0)
    assert result.blocks == []
    assert "ocr_not_configured" in result.warnings


def test_dockerfile_includes_ocr_adapter():
    from pathlib import Path

    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "ocr_adapter.py" in dockerfile
