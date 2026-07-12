"""Tests for parser module: PDF question extraction."""
import pytest
import fitz

import config
from parser import PDFProcessingError, Question, normalize_worksheet_text, parse_pdf


def test_parse_pdf_question_format(tmp_pdf_question_format):
    """Parser extracts questions from 'Question N:' lines."""
    path = tmp_pdf_question_format
    title, questions = parse_pdf(path)
    assert title
    assert len(questions) >= 2
    ids = [q.id for q in questions]
    assert 1 in ids
    assert 2 in ids
    q1 = next(q for q in questions if q.id == 1)
    assert "3x + 7" in q1.text or "Solve" in q1.text


def test_parse_pdf_question_dot_format(tmp_path):
    """Parser extracts questions from 'Question N.' lines."""
    path = tmp_path / "question_dot.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Worksheet", fontsize=14)
    page.insert_text((72, 100), "Question 1. Solve for x", fontsize=12)
    page.insert_text((72, 120), "Question 2. Explain your answer", fontsize=12)
    doc.save(str(path))
    doc.close()

    _, questions = parse_pdf(path)

    assert [q.id for q in questions] == [1, 2]
    assert questions[0].text == "Solve for x"


def test_parse_pdf_returns_question_objects(tmp_pdf_question_format):
    """Parser returns Question dataclass instances with id and text."""
    _, questions = parse_pdf(tmp_pdf_question_format)
    for q in questions:
        assert isinstance(q, Question)
        assert isinstance(q.id, int)
        assert isinstance(q.text, str)


def test_parse_pdf_numbered_format(tmp_pdf_numbered_format):
    """Parser extracts questions from '1.', '2.' numbered lines."""
    _, questions = parse_pdf(tmp_pdf_numbered_format)
    assert len(questions) >= 2
    ids = [q.id for q in questions]
    assert 1 in ids
    assert 2 in ids


def test_parse_pdf_parenthesized_numbered_format(tmp_path):
    """Parser extracts questions from '1)', '2)' numbered lines."""
    path = tmp_path / "parenthesized_numbered.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Worksheet", fontsize=14)
    page.insert_text((72, 100), "1) First parenthesized prompt", fontsize=12)
    page.insert_text((72, 120), "2) Second parenthesized prompt", fontsize=12)
    doc.save(str(path))
    doc.close()

    _, questions = parse_pdf(path)

    assert [q.id for q in questions] == [1, 2]
    assert questions[0].text == "First parenthesized prompt"


def test_parse_pdf_fallback_single_block(tmp_pdf_no_questions):
    """When no question pattern matches, parser returns single question with id=0."""
    title, questions = parse_pdf(tmp_pdf_no_questions)
    assert len(questions) == 1
    assert questions[0].id == 0
    assert "paragraph" in questions[0].text or "text" in questions[0].text.lower()


def test_parse_pdf_question_double_digit(tmp_pdf_question_double_digit):
    """Parser preserves double-digit Question ids (e.g. 10)."""
    _, questions = parse_pdf(tmp_pdf_question_double_digit)
    ids = {q.id for q in questions}
    assert 1 in ids
    assert 10 in ids
    q10 = next(q for q in questions if q.id == 10)
    assert "Tenth" in q10.text or "tenth" in q10.text.lower()


def test_parse_pdf_question_multiline_continuation(tmp_pdf_question_multiline):
    """Lines after Question 1: without a new Question header merge into question 1."""
    _, questions = parse_pdf(tmp_pdf_question_multiline)
    assert len(questions) >= 2
    q1 = next(q for q in questions if q.id == 1)
    assert "Start of problem" in q1.text
    assert "continuation" in q1.text.lower()


def test_parse_pdf_numbered_continuation_merged(tmp_pdf_numbered_with_continuation):
    """Non-numbered line after '1.' is merged into question 1 until '2.'."""
    _, questions = parse_pdf(tmp_pdf_numbered_with_continuation)
    assert len(questions) >= 2
    q1 = next(q for q in questions if q.id == 1)
    assert "Alpha" in q1.text
    assert "Extra detail" in q1.text or "extra detail" in q1.text.lower()


def test_normalize_worksheet_text_empty():
    assert normalize_worksheet_text("") == ""
    assert normalize_worksheet_text(None) is None


def test_parse_pdf_rejects_page_limit(tmp_path, monkeypatch):
    path = tmp_path / "many-pages.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    monkeypatch.setattr(config, "MAX_PDF_PAGES", 1)

    with pytest.raises(PDFProcessingError, match="page count"):
        parse_pdf(path)


def test_parse_pdf_rejects_extracted_text_limit(tmp_pdf_question_format, monkeypatch):
    monkeypatch.setattr(config, "MAX_EXTRACTED_TEXT_CHARS", 8)

    with pytest.raises(PDFProcessingError, match="extracted text"):
        parse_pdf(tmp_pdf_question_format)
