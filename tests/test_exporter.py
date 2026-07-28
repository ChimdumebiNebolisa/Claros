"""Tests for exporter module: PDF export with questions and answers."""
import fitz
import pytest

from exporter import (
    UnsupportedAnswerTextError,
    build_export_pdf,
    build_layout_export_pdf,
    build_original_export_pdf,
)


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return " ".join(page.get_text() for page in doc)
    finally:
        doc.close()


def test_build_export_pdf_returns_bytes():
    """build_export_pdf returns non-empty PDF bytes."""
    questions = [{"id": 1, "text": "What is 2+2?"}, {"id": 2, "text": "What is 3+3?"}]
    answers = [
        {"question_id": 1, "answer_text": "4"},
        {"question_id": 2, "answer_text": "6"},
    ]
    pdf_bytes = build_export_pdf("Test Assignment", questions, answers)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
    assert pdf_bytes.startswith(b"%PDF")


def test_build_export_pdf_includes_title_and_answers():
    """Exported PDF contains assignment title and written answers."""
    questions = [{"id": 1, "text": "Solve for x."}]
    answers = [{"question_id": 1, "answer_text": "x = 5"}]
    pdf_bytes = build_export_pdf("Algebra Quiz", questions, answers)
    text = _pdf_text(pdf_bytes)
    assert "Algebra" in text
    assert "x = 5" in text


def test_build_export_pdf_no_answer_shows_placeholder():
    """Missing answer is rendered as (No answer)."""
    questions = [{"id": 1, "text": "Question one."}]
    answers = []  # no answers
    pdf_bytes = build_export_pdf("Title", questions, answers)
    text = _pdf_text(pdf_bytes)
    assert "No answer" in text


def test_build_export_pdf_preserves_literal_latex_dollars():
    """Confirmed answer text is not reformatted during legacy PDF export."""
    questions = [{"id": 1, "text": "Solve for x."}]
    answers = [{"question_id": 1, "answer_text": "$x = 5$"}]
    pdf_bytes = build_export_pdf("Math", questions, answers)
    text = _pdf_text(pdf_bytes)
    assert "$x = 5$" in text


def test_build_export_pdf_unicode_minus_in_body():
    """Unicode minus in question/answer text does not break export."""
    questions = [{"id": 1, "text": "Solve x \u2212 3 = 5"}]
    answers = [{"question_id": 1, "answer_text": "x = 8"}]
    pdf_bytes = build_export_pdf("Quiz", questions, answers)
    text = _pdf_text(pdf_bytes)
    assert "Solve x" in text
    assert "3 = 5" in text


def test_original_export_preserves_page_and_writes_answer():
    source = fitz.open()
    page = source.new_page(width=612, height=792)
    page.insert_text((72, 72), "Original Worksheet", fontsize=16)
    page.insert_text((72, 120), "Question 1: Solve 2 + 2", fontsize=12)
    original_bytes = source.tobytes()
    source.close()
    questions = [
        {
            "id": 1,
            "text": "Solve 2 + 2",
            "page": 1,
            "answer_region": {"x": 0.12, "y": 0.2, "width": 0.45, "height": 0.08},
        }
    ]

    exported = build_original_export_pdf(
        original_bytes,
        questions,
        [{"question_id": 1, "answer_text": "4"}],
    )

    document = fitz.open(stream=exported, filetype="pdf")
    try:
        assert document.page_count == 1
        text = document[0].get_text()
    finally:
        document.close()
    assert "Original Worksheet" in text
    assert "4" in text


def test_original_export_does_not_use_unreviewed_manifest_region_without_confirmation():
    source = fitz.open()
    page = source.new_page(width=612, height=792)
    page.insert_text((72, 72), "Original Worksheet", fontsize=16)
    original_bytes = source.tobytes()
    source.close()
    region = {"x": 0.12, "y": 0.2, "width": 0.45, "height": 0.08}
    questions = [
        {
            "id": 1,
            "text": "Explain",
            "page": 1,
            "answer_region": region,
            "needs_layout_review": True,
        }
    ]

    safe_fallback = build_original_export_pdf(
        original_bytes,
        questions,
        [{"question_id": 1, "answer_text": "Confirmed answer"}],
    )
    document = fitz.open(stream=safe_fallback, filetype="pdf")
    try:
        assert document.page_count == 2
        assert "Confirmed answer" not in document[0].get_text()
        assert "Confirmed answer" in document[1].get_text()
    finally:
        document.close()

    explicit_confirmation = build_original_export_pdf(
        original_bytes,
        questions,
        [{"question_id": 1, "answer_text": "Confirmed answer", "answer_region": region}],
    )
    document = fitz.open(stream=explicit_confirmation, filetype="pdf")
    try:
        assert document.page_count == 1
        assert "Confirmed answer" in document[0].get_text()
    finally:
        document.close()


def test_original_export_paginates_long_side_panel_answers_without_truncation():
    source = fitz.open()
    source.new_page(width=612, height=792)
    original_bytes = source.tobytes()
    source.close()
    answer = "lorem ipsum " * 350

    exported = build_original_export_pdf(
        original_bytes,
        [{"id": 1, "text": "Explain", "page": 1, "answer_region": None}],
        [{"question_id": 1, "answer_text": answer}],
    )

    document = fitz.open(stream=exported, filetype="pdf")
    try:
        extracted = " ".join(page.get_text() for page in document)
        assert document.page_count > 2
    finally:
        document.close()
    assert extracted.count("lorem") == 350


def test_original_export_preserves_literal_math_and_unicode_in_a_physical_region():
    source = fitz.open()
    source.new_page(width=612, height=792)
    original_bytes = source.tobytes()
    source.close()
    answer = "Case $x$  \u03c0"

    exported = build_original_export_pdf(
        original_bytes,
        [{"id": 1, "text": "Explain", "page": 1, "answer_region": {"x": 0.1, "y": 0.2, "width": 0.6, "height": 0.1}}],
        [{"question_id": 1, "answer_text": answer}],
    )

    assert answer in _pdf_text(exported)


def test_layout_export_preserves_literal_math_and_unicode():
    source = fitz.open()
    source.new_page(width=612, height=792)
    original_bytes = source.tobytes()
    source.close()
    answer = "Case $x$  \u03c0"

    exported = build_layout_export_pdf(
        original_bytes,
        [{"id": 1, "page_index": 0, "answer_bbox": [72, 144, 396, 216]}],
        [{"question_id": 1, "answer_text": answer}],
        pages=[{"page_index": 0, "width_points": 612, "height_points": 792}],
    )

    assert answer in _pdf_text(exported)


def test_export_rejects_unsupported_confirmed_text_instead_of_substituting_glyphs():
    source = fitz.open()
    source.new_page(width=612, height=792)
    original_bytes = source.tobytes()
    source.close()

    with pytest.raises(UnsupportedAnswerTextError):
        build_original_export_pdf(
            original_bytes,
            [{"id": 1, "text": "Explain", "page": 1, "answer_region": None}],
            [{"question_id": 1, "answer_text": "Unsupported \U0001f642"}],
        )
