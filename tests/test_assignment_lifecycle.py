"""Stage 11 lifecycle and privacy regression tests."""
from __future__ import annotations

import pytest

import config
import storage


@pytest.fixture
def local_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_STORAGE_DIR", str(tmp_path / ".claros-data"))
    return tmp_path / ".claros-data"


def test_assignment_delete_continues_after_session_cleanup_failure(local_storage, monkeypatch):
    assignment_id = "a1111111-1111-4111-8111-111111111111"
    session_id = "b2222222-2222-4222-8222-222222222222"
    storage.upload_pdf_to_gcs(assignment_id, b"%PDF-1.4 orphan")
    storage.register_assignment_session(assignment_id, session_id)
    storage.upload_session_to_gcs(session_id, b'{"session_id":"b2222222-2222-4222-8222-222222222222"}')

    def boom(_session_id):
        raise RuntimeError("simulated session delete failure")

    monkeypatch.setattr(storage, "delete_session_from_gcs", boom)
    storage.delete_assignment_and_sessions(assignment_id)

    assert not (local_storage / "assignments" / assignment_id / "assignment.pdf").exists()
    assert storage.list_assignment_session_ids(assignment_id) == []


def test_session_cleanup_metric_labels_are_supported():
    from observability import EVENTS, REASONS, record_metric

    assert "session_cleanup" in EVENTS
    assert "assignment_deleted" in EVENTS
    assert "assignment_expired" in EVENTS
    assert "assignment_delete" in REASONS
    record_metric("session_cleanup", status="error", reason="assignment_delete")
    record_metric("assignment_deleted", status="ok", reason="assignment_delete")
    record_metric("assignment_expired", status="expired")
