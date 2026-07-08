"""Unit tests for deterministic GCS PDF selection in load_assignment_from_gcs."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import assignment_service
from tests.conftest import TEST_ASSIGNMENT_ID


class _FakeBlob:
    def __init__(self, name: str):
        self.name = name

    def download_as_bytes(self):
        return b"%PDF-1.4 fake"


def test_load_assignment_picks_pdf_sorted_by_name(monkeypatch, tmp_path):
    """When multiple blobs exist, the .pdf with the lexicographically first name is used."""
    blobs = [
        _FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/notes.txt"),
        _FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/worksheet.pdf"),
        _FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/assignment.pdf"),
    ]

    bucket = MagicMock()
    bucket.list_blobs.return_value = blobs

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)

    def fake_parse(path):
        return "Title", [SimpleNamespace(id=1, text="Q?")]

    monkeypatch.setattr(assignment_service, "parse_pdf", fake_parse)

    title, questions = assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)

    assert title == "Title"
    assert questions == [{"id": 1, "text": "Q?"}]
    bucket.list_blobs.assert_called_once_with(prefix=f"assignments/{TEST_ASSIGNMENT_ID}/")


def test_load_assignment_raises_when_no_pdf(monkeypatch):
    bucket = MagicMock()
    bucket.list_blobs.return_value = [_FakeBlob(f"assignments/{TEST_ASSIGNMENT_ID}/readme.txt")]

    monkeypatch.setattr(assignment_service, "get_gcs_bucket", lambda: bucket)

    with pytest.raises(ValueError, match="No PDF found"):
        assignment_service.load_assignment_from_gcs(TEST_ASSIGNMENT_ID)
