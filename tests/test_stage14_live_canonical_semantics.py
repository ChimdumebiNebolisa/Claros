"""Optional Stage 14 live Gemini semantics check for canonical_v1 PDFs.

Skipped unless CLAROS_LIVE_SEMANTICS=1 and GEMINI_API_KEY is set.
Does not modify expected labels or manifests.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PDFS = [
    ROOT
    / "evaluation"
    / "canonical_v1"
    / "generated"
    / "pdfs"
    / "canonical-short-answer-ecosystems.pdf",
    ROOT
    / "evaluation"
    / "canonical_v1"
    / "generated"
    / "pdfs"
    / "canonical-choice-digital-safety.pdf",
    ROOT
    / "evaluation"
    / "canonical_v1"
    / "generated"
    / "pdfs"
    / "canonical-numeric-everyday-math.pdf",
]


def _live_enabled() -> bool:
    return os.environ.get("CLAROS_LIVE_SEMANTICS", "").strip() == "1" and bool(
        os.environ.get("GEMINI_API_KEY", "").strip()
    )


@pytest.mark.skipif(not _live_enabled(), reason="Set CLAROS_LIVE_SEMANTICS=1 and GEMINI_API_KEY to run")
def test_live_gemini_semantics_finds_tasks_on_canonical_pdfs():
    from document_pipeline import parse_document
    from semantic_classifier import GeminiSemanticClassifier

    classifier = GeminiSemanticClassifier()
    for pdf_path in CANONICAL_PDFS:
        assert pdf_path.is_file(), f"missing {pdf_path}"
        parsed = parse_document(pdf_path.read_bytes(), semantic_classifier=classifier)
        assert len(parsed.tasks) >= 2, (
            f"{pdf_path.name}: expected multiple tasks from live Gemini, got {len(parsed.tasks)}; "
            f"warnings={parsed.warnings}"
        )
