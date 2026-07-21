"""Worksheet layout, preview, and original-PDF export coverage for the rebuilt pipeline."""
from __future__ import annotations

import fitz
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
from exporter import build_original_export_pdf
from manifest import build_manifest, validate_bbox_within_page
from parser import parse_pdf_with_diagnostics
from schemas import validate_layout_overrides
from tests.conftest import TEST_ASSIGNMENT_ID
from tests.layout_fixtures import (
    write_answer_lines,
    write_simple_one_column,
    write_unicode_math,
)

client = TestClient(main_module.app)


def test_validate_bbox_rejects_nan_and_outside_page():
    with pytest.raises(ValueError):
        validate_bbox_within_page([0, 0, float("nan"), 10], page_width=100, page_height=100)
    with pytest.raises(ValueError):
        validate_bbox_within_page([0, 0, 200, 50], page_width=100, page_height=100)


def test_simple_one_column_layout(tmp_path):
    path = write_simple_one_column(tmp_path / "simple.pdf")
    title, questions, warnings, status = parse_pdf_with_diagnostics(path)
    assert status == "layout_review_required"
    assert title
    assert [q.id for q in questions] == [1, 2]
    for question in questions:
        assert question.page == 1
        assert 0.0 <= question.layout_confidence <= 1.0
    assert questions[0].answer_region is not None
    assert questions[1].answer_region is None


def test_answer_lines_fixture_detects_regions(tmp_path):
    path = write_answer_lines(tmp_path / "lines.pdf")
    _title, questions, _warnings, status = parse_pdf_with_diagnostics(path)
    assert status == "ok"
    assert questions
    assert all(q.answer_region for q in questions)


def test_unicode_math_normalized(tmp_path):
    path = write_unicode_math(tmp_path / "unicode.pdf")
    _title, questions, _warnings, _status = parse_pdf_with_diagnostics(path)
    assert questions
    assert "\u2212" not in questions[0].text


def test_original_export_preserves_page_and_writes_answer(tmp_path):
    path = write_simple_one_column(tmp_path / "export_src.pdf")
    _title, questions, _warnings, _status = parse_pdf_with_diagnostics(path)
    q1 = next(q for q in questions if q.id == 1)
    out = build_original_export_pdf(
        path.read_bytes(),
        [
            {
                "id": q.id,
                "text": q.text,
                "page": q.page,
                "answer_region": q.answer_region,
            }
            for q in questions
        ],
        [{"question_id": 1, "answer_text": "x = 5", "answer_region": q1.answer_region}],
    )
    doc = fitz.open(stream=out, filetype="pdf")
    try:
        assert doc.page_count == 1
        text = doc[0].get_text()
        assert "x = 5" in text
    finally:
        doc.close()


def test_invalid_override_outside_page_rejected_by_schema():
    with pytest.raises(Exception):
        validate_layout_overrides(
            [{"question_id": 1, "page_index": 0, "answer_bbox": [0, 0, -10, 20]}]
        )


def test_preview_route_happy_path(monkeypatch, tmp_path):
    path = write_simple_one_column(tmp_path / "preview.pdf")
    pdf_bytes = path.read_bytes()
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
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: pdf_bytes)
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/1.png")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_preview_rejects_invalid_page(monkeypatch, tmp_path):
    path = write_simple_one_column(tmp_path / "preview2.pdf")
    title, questions, warnings, status = parse_pdf_with_diagnostics(path)
    manifest = build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title=title,
        questions=[],
        parse_status=status,
        parse_warnings=warnings,
        page_count=1,
    )
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: path.read_bytes())
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/99.png")
    assert response.status_code == 404


def test_preview_rejects_expired(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_manifest",
        lambda _id: (_ for _ in ()).throw(assignment_service.AssignmentExpiredError("expired")),
    )
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/1.png")
    assert response.status_code == 410


def test_ocr_adapter_null_boundary():
    from ocr_adapter import get_ocr_adapter

    result = get_ocr_adapter().extract_page_text(b"%PDF", 0)
    assert result.blocks == []
    assert "ocr_not_configured" in result.warnings


def test_dockerfile_includes_ocr_adapter():
    from pathlib import Path

    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "ocr_adapter.py" in dockerfile
