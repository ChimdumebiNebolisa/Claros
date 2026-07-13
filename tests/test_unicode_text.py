"""Regression tests for Unicode worksheet text (parser, upload path, export)."""
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate
from fastapi.testclient import TestClient

from exporter import build_export_pdf
from parser import normalize_worksheet_text, parse_pdf

import assignment_service
import main as main_module


def _write_unicode_minus_pdf(path) -> None:
    """Build a PDF with a true Unicode minus (ReportLab preserves it on extract)."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    story = [
        Paragraph("Unicode Sheet", styles["Normal"]),
        Paragraph("Question 1: Solve x \u2212 3 = 5", styles["Normal"]),
    ]
    doc.build(story)


def test_normalize_worksheet_text_unicode_punctuation():
    raw = "Solve x \u2212 3 = 5 \u201cquick\u201d \u2018check\u2019 dash\u2014here"
    norm = normalize_worksheet_text(raw)
    assert norm == 'Solve x - 3 = 5 "quick" \'check\' dash-here'
    assert "\u2212" not in norm
    assert "\u2014" not in norm
    assert "\u00a0" not in normalize_worksheet_text("a\u00a0b")


def test_parse_pdf_unicode_minus_normalized(tmp_path):
    path = tmp_path / "unicode_minus.pdf"
    _write_unicode_minus_pdf(path)

    _, questions = parse_pdf(path)
    assert len(questions) == 1
    assert "\u2212" not in questions[0].text
    assert re.search(r"Solve x\s*-\s*3 = 5", questions[0].text)


def test_parse_test_assignment_pdf_no_unicode_minus_in_output():
    """Shipped sample PDF contains Unicode minus; parser must normalize it."""
    _, questions = parse_pdf("test_assignment.pdf")
    assert questions
    combined = " ".join(q.text for q in questions)
    assert "\u2212" not in combined
    assert "-" in combined


def test_upload_unicode_pdf_does_not_fail_charmap(monkeypatch, tmp_path):
    """POST /upload debug logging must not raise UnicodeEncodeError on Windows."""
    path = tmp_path / "upload_unicode.pdf"
    _write_unicode_minus_pdf(path)

    # persist_assignment_from_pdf_bytes imports these names into the assignment_service
    # namespace, so patch them there (patching storage.* would not affect the bound names).
    monkeypatch.setattr(assignment_service, "upload_pdf_to_gcs", lambda *args, **kwargs: "gs://fake/b.pdf")
    monkeypatch.setattr(assignment_service, "upload_manifest_to_gcs", lambda *args, **kwargs: None)

    client = TestClient(main_module.app)
    response = client.post(
        "/upload",
        files={"file": ("worksheet.pdf", path.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "\u2212" not in data["questions"][0]["text"]
    assert re.search(r"Solve x\s*-\s*3 = 5", data["questions"][0]["text"])


def test_build_export_pdf_unicode_minus_no_crash():
    questions = [{"id": 1, "text": "Solve x \u2212 3 = 5"}]
    answers = [{"question_id": 1, "answer_text": "x = 8"}]
    pdf_bytes = build_export_pdf("Algebra \u2013 Quiz", questions, answers)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 100
