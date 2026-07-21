"""Unit tests for deterministic GCS PDF selection in load_assignment_from_gcs."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import fitz
import pytest

import assignment_service
import config
from storage import assignment_pdf_path
from tests.conftest import TEST_ASSIGNMENT_ID


class _FakeBlob:
    def __init__(self, name: str, exists: bool = True):
        self.name = name
        self._exists = exists

    def exists(self):
        return self._exists

    def download_as_bytes(self):
        document = fitz.open()
        document.new_page()
        try:
            return document.tobytes()
        finally:
            document.close()


def _fake_parse_with_diagnostics(_path):
    question = SimpleNamespace(
        id=1,
        text="Q?",
        page=1,
        prompt_region=None,
        answer_region=None,
        detected_answer_region=None,
        layout_confidence=0.0,
        needs_layout_review=True,
    )
    return ("Title", [question], [], "ok")


def test_load_assignment_prefers_canonical_assignment_pdf(monkeypatch):
    """Canonical assignments/{id}/assignment.pdf is used when present."""
    canonical = _FakeBlob(assignment_pdf_path(TEST_ASSIGNMENT_ID))
    bucket = MagicMock()
    bucket.blob.return_value = canonical

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)
    monkeypatch.setattr(assignment_service, "download_manifest_from_gcs", lambda _id: None)
    monkeypatch.setattr(assignment_service, "parse_pdf_with_diagnostics", _fake_parse_with_diagnostics)
    monkeypatch.setattr(assignment_service, "upload_manifest_to_gcs", lambda *_a, **_k: "gs://x")
    monkeypatch.setattr(config, "PDF_PARSER_MODE", "legacy")

    title, questions = assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)

    assert title == "Title"
    assert len(questions) == 1
    assert questions[0]["id"] == 1
    assert questions[0]["text"] == "Q?"
    assert questions[0]["needs_layout_review"] is True
    assert questions[0]["answer_region_status"] == "side_panel"
    bucket.blob.assert_called_with(assignment_pdf_path(TEST_ASSIGNMENT_ID))


def test_load_assignment_falls_back_to_sorted_pdf(monkeypatch):
    """Legacy uploads without canonical key still resolve via sorted .pdf list."""
    blobs = [
        _FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/notes.txt", exists=False),
        _FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/worksheet.pdf"),
        _FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/assignment.pdf"),
    ]
    canonical = _FakeBlob(assignment_pdf_path(TEST_ASSIGNMENT_ID), exists=False)

    bucket = MagicMock()
    bucket.blob.return_value = canonical
    bucket.list_blobs.return_value = blobs

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)
    monkeypatch.setattr(assignment_service, "download_manifest_from_gcs", lambda _id: None)
    monkeypatch.setattr(assignment_service, "parse_pdf_with_diagnostics", _fake_parse_with_diagnostics)
    monkeypatch.setattr(assignment_service, "upload_manifest_to_gcs", lambda *_a, **_k: "gs://x")
    monkeypatch.setattr(config, "PDF_PARSER_MODE", "legacy")

    title, questions = assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)

    assert title == "Title"
    assert len(questions) == 1
    assert questions[0]["id"] == 1
    assert questions[0]["text"] == "Q?"
    assert questions[0]["needs_layout_review"] is True
    assert questions[0]["answer_region_status"] == "side_panel"
    bucket.list_blobs.assert_called_once_with(prefix=f"assignments/{TEST_ASSIGNMENT_ID}/")


def test_load_assignment_raises_when_no_pdf(monkeypatch):
    canonical = _FakeBlob(assignment_pdf_path(TEST_ASSIGNMENT_ID), exists=False)
    bucket = MagicMock()
    bucket.blob.return_value = canonical
    bucket.list_blobs.return_value = [_FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/readme.txt", exists=False)]

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)
    monkeypatch.setattr(assignment_service, "download_manifest_from_gcs", lambda _id: None)

    with pytest.raises(ValueError, match="No PDF found"):
        assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)
