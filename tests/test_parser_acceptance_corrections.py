"""Regression coverage derived from the 20-file PDF acceptance baseline."""
from __future__ import annotations

import fitz
from fastapi.testclient import TestClient

import assignment_service
import config
import main as main_module
from parser import parse_pdf_with_diagnostics
from tests.conftest import TEST_ASSIGNMENT_ID
from tests.layout_fixtures import write_image_only


def _save_lines(path, pages: list[list[tuple[float, float, str]]]):
    doc = fitz.open()
    for page_lines in pages:
        page = doc.new_page(width=612, height=792)
        for x, y, text in page_lines:
            page.insert_text((x, y), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def test_image_only_pdf_requires_ocr_and_has_no_questions(tmp_path):
    path = write_image_only(tmp_path / "scan.pdf")

    _title, questions, warnings, status = parse_pdf_with_diagnostics(path)

    assert status == "requires_ocr"
    assert questions == []
    assert "requires_ocr" in warnings


def test_text_without_clear_questions_is_unsupported_without_fallback(tmp_pdf_no_questions):
    _title, questions, warnings, status = parse_pdf_with_diagnostics(tmp_pdf_no_questions)

    assert status == "unsupported_layout"
    assert questions == []
    assert "unsupported_layout" in warnings


def test_compound_labels_get_unique_ids_and_correct_pages(tmp_path):
    path = _save_lines(
        tmp_path / "compound.pdf",
        [
            [
                (72, 72, "Student Worksheet"),
                (72, 120, "3a. How do sessile organisms get food?"),
                (72, 170, "Answer: ______________________________"),
            ],
            [
                (72, 72, "Student Worksheet continued"),
                (72, 120, "3b. What is the driving question?"),
                (72, 170, "Answer: ______________________________"),
            ],
        ],
    )

    _title, questions, _warnings, status = parse_pdf_with_diagnostics(path)

    assert status == "ok"
    assert [q.id for q in questions] == [1, 2]
    assert [q.label for q in questions] == ["3a", "3b"]
    assert [q.page for q in questions] == [1, 2]
    assert len({q.id for q in questions}) == 2


def test_numeric_values_urls_scientific_notation_and_procedures_are_not_questions(tmp_path):
    path = _save_lines(
        tmp_path / "false-labels.pdf",
        [
            [
                (72, 72, "Student Worksheet"),
                (72, 105, "0.001"),
                (72, 125, "7.0 x 10^13"),
                (72, 145, "1. Put on safety goggles."),
                (72, 165, "2. https://example.org/activity"),
                (72, 210, "3. What is 2 + 2?"),
                (72, 250, "Answer: ______________________________"),
                (72, 310, "4. Explain your reasoning."),
                (72, 350, "Answer: ______________________________"),
            ],
        ],
    )

    _title, questions, _warnings, status = parse_pdf_with_diagnostics(path)

    assert status == "ok"
    assert [q.label for q in questions] == ["3", "4"]
    assert all("goggles" not in q.text and "example.org" not in q.text for q in questions)


def test_explicit_student_section_excludes_educator_and_answer_key_items(tmp_path):
    path = _save_lines(
        tmp_path / "mixed-sections.pdf",
        [
            [
                (72, 72, "Teacher Guide"),
                (72, 105, "Materials"),
                (72, 130, "1. Copy the student worksheet."),
                (72, 155, "2. Gather materials."),
            ],
            [
                (72, 72, "Student Worksheet"),
                (72, 130, "1. Why is clean water important?"),
                (72, 180, "Answer: ______________________________"),
            ],
            [
                (72, 72, "Teacher Answer Key"),
                (72, 130, "1. Clean water protects health."),
            ],
        ],
    )

    _title, questions, warnings, status = parse_pdf_with_diagnostics(path)

    assert status == "layout_review_required"
    assert [q.text for q in questions] == ["Why is clean water important?"]
    assert [q.page for q in questions] == [2]
    assert "mixed_educator_student_packet" in warnings


def test_low_confidence_answer_region_is_suppressed_and_requires_review(tmp_path):
    path = _save_lines(
        tmp_path / "uncertain-region.pdf",
        [[(72, 72, "Student Worksheet"), (72, 130, "Question 1: Explain resonance?")]],
    )

    _title, questions, warnings, status = parse_pdf_with_diagnostics(path)

    assert status == "layout_review_required"
    assert len(questions) == 1
    assert questions[0].answer_region is None
    assert questions[0].detected_answer_region is None
    assert questions[0].needs_layout_review is True
    assert "layout_review_required" in warnings


def test_write_rejects_client_confirmed_layout(monkeypatch):
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", False)
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: (
            "Worksheet",
            [
                {
                    "id": 1,
                    "label": "1",
                    "text": "Explain resonance?",
                    "page": 1,
                    "answer_region": None,
                    "needs_layout_review": True,
                }
            ],
        ),
    )
    client = TestClient(main_module.app)

    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "answer_candidate": "A response",
            "layout_confirmed": True,
            "answer_region": {"x": 0.2, "y": 0.2, "width": 0.2, "height": 0.05},
        },
    )

    assert response.status_code == 409
    assert "layout" in response.json()["detail"].lower()
