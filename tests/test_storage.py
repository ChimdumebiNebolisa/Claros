"""Storage helper tests."""
import threading
import time
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import PreconditionFailed

import storage


def test_assignment_pdf_path_uses_canonical_filename():
    assignment_id = "550e8400-e29b-41d4-a716-446655440000"
    assert storage.assignment_pdf_path(assignment_id) == (
        f"assignments/{assignment_id}/{storage.CANONICAL_PDF_NAME}"
    )


def test_assignment_manifest_path():
    assignment_id = "550e8400-e29b-41d4-a716-446655440000"
    assert storage.assignment_manifest_path(assignment_id) == (
        f"assignments/{assignment_id}/manifest.json"
    )


def test_upload_pdf_to_gcs_uploads_canonical_blob(monkeypatch):
    bucket = MagicMock()
    blob = MagicMock()
    bucket.blob.return_value = blob
    bucket.name = "claros-bucket"
    monkeypatch.setattr(storage, "get_gcs_bucket", lambda: bucket)

    path = storage.upload_pdf_to_gcs("550e8400-e29b-41d4-a716-446655440000", b"%PDF-1.4")

    bucket.blob.assert_called_once_with(
        "assignments/550e8400-e29b-41d4-a716-446655440000/assignment.pdf"
    )
    blob.upload_from_string.assert_called_once_with(b"%PDF-1.4", content_type="application/pdf")
    assert path.endswith("/assignments/550e8400-e29b-41d4-a716-446655440000/assignment.pdf")


def test_session_upload_uses_generation_precondition(monkeypatch):
    bucket = MagicMock()
    blob = MagicMock()
    blob.generation = 9
    bucket.blob.return_value = blob
    bucket.name = "claros-bucket"
    monkeypatch.setattr(storage, "get_gcs_bucket", lambda: bucket)

    result = storage.upload_session_to_gcs("session-1", b"{}", if_generation_match=8, return_generation=True)

    blob.upload_from_string.assert_called_once_with(
        b"{}",
        content_type="application/json",
        if_generation_match=8,
    )
    assert result == ("gs://claros-bucket/sessions/session-1.json", 9)


def test_session_upload_maps_gcs_precondition_failure(monkeypatch):
    bucket = MagicMock()
    blob = MagicMock()
    blob.upload_from_string.side_effect = PreconditionFailed("conflict")
    bucket.blob.return_value = blob
    bucket.name = "claros-bucket"
    monkeypatch.setattr(storage, "get_gcs_bucket", lambda: bucket)

    with pytest.raises(storage.StorageConflict):
        storage.upload_session_to_gcs("session-1", b"{}", if_generation_match=8)


def test_local_session_generation_precondition_allows_only_one_concurrent_writer(monkeypatch, tmp_path):
    monkeypatch.setattr(storage.config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage.config, "LOCAL_STORAGE_DIR", str(tmp_path))
    storage.upload_session_to_gcs("session-1", b'{"version": 1}')
    _payload, generation = storage.download_session_from_gcs("session-1", with_generation=True)

    original_atomic_write = storage._atomic_write

    def slow_atomic_write(path, payload):
        time.sleep(0.05)
        original_atomic_write(path, payload)

    monkeypatch.setattr(storage, "_atomic_write", slow_atomic_write)
    barrier = threading.Barrier(2)
    outcomes = []

    def write(payload):
        barrier.wait(timeout=2)
        try:
            storage.upload_session_to_gcs("session-1", payload, if_generation_match=generation)
            outcomes.append("ok")
        except storage.StorageConflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=write, args=(payload,)) for payload in (b'{"writer": "a"}', b'{"writer": "b"}')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(outcomes) == ["conflict", "ok"]
