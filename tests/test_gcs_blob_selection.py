"""Unit tests for deterministic GCS PDF selection in load_assignment_from_gcs."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import assignment_service
from storage import assignment_pdf_path
from tests.conftest import TEST_ASSIGNMENT_ID


class _FakeBlob:
    def __init__(self, name: str, exists: bool = True):
        self.name = name
        self._exists = exists

    def exists(self):
        return self._exists

    def download_as_bytes(self):
        return b"%PDF-1.4 fake"


def test_load_assignment_prefers_canonical_assignment_pdf(monkeypatch):
    """Canonical assignments/{id}/assignment.pdf is used when present."""
    canonical = _FakeBlob(assignment_pdf_path(TEST_ASSIGNMENT_ID))
    bucket = MagicMock()
    bucket.blob.return_value = canonical

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)
    monkeypatch.setattr(
        assignment_service,
        "parse_pdf",
        lambda _path: ("Title", [SimpleNamespace(id=1, text="Q?")]),
    )

    title, questions = assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)

    assert title == "Title"
    assert questions == [{"id": 1, "text": "Q?"}]
    bucket.blob.assert_called_once_with(assignment_pdf_path(TEST_ASSIGNMENT_ID))
    bucket.list_blobs.assert_not_called()


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
    monkeypatch.setattr(
        assignment_service,
        "parse_pdf",
        lambda _path: ("Title", [SimpleNamespace(id=1, text="Q?")]),
    )

    title, questions = assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)

    assert title == "Title"
    assert questions == [{"id": 1, "text": "Q?"}]
    bucket.list_blobs.assert_called_once_with(prefix=f"assignments/{TEST_ASSIGNMENT_ID}/")


def test_load_assignment_raises_when_no_pdf(monkeypatch):
    canonical = _FakeBlob(assignment_pdf_path(TEST_ASSIGNMENT_ID), exists=False)
    bucket = MagicMock()
    bucket.blob.return_value = canonical
    bucket.list_blobs.return_value = [_FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/readme.txt", exists=False)]

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)

    with pytest.raises(ValueError, match="No PDF found"):
        assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)
