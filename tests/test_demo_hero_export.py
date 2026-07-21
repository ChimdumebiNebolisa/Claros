from pathlib import Path

import fitz

from demo.hero_fixture import manifest_questions
from exporter import build_original_export_pdf


def test_hero_export_preserves_original_page_and_routes_uncertain_task_to_side_panel():
    source_pdf = Path("demo/hero_worksheet.pdf").read_bytes()
    questions = manifest_questions(source_pdf)
    assert questions is not None

    exported = build_original_export_pdf(
        source_pdf,
        questions,
        [
            {"question_id": 2, "answer_text": "A cold, oxygen-rich stream."},
            {"question_id": 4, "answer_text": "algae -> insect -> fish"},
        ],
    )

    document = fitz.open(stream=exported, filetype="pdf")
    try:
        assert document.page_count == 2
        assert "River Habitat Investigation" in document[0].get_text()
        assert "A cold, oxygen-rich stream." in document[0].get_text()
        assert "algae -> insect -> fish" in document[1].get_text()
        assert "Claros confirmed answers (side panel)" in document[1].get_text()
    finally:
        document.close()
