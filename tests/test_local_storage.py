from pathlib import Path

import pytest

import config
import storage


@pytest.fixture
def local_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_STORAGE_DIR", str(tmp_path / ".claros-data"))
    return tmp_path / ".claros-data"


def test_local_storage_round_trips_assignment_manifest_and_session(local_storage):
    assignment_id = "550e8400-e29b-41d4-a716-446655440000"
    session_id = "550e8400-e29b-41d4-a716-446655440001"
    pdf = b"%PDF-1.4\nfixture"

    storage.upload_pdf_to_gcs(assignment_id, pdf)
    storage.upload_manifest_to_gcs(assignment_id, '{"assignment_id":"fixture"}')
    storage.upload_session_to_gcs(session_id, b'{"session_id":"fixture"}')

    assert storage.download_pdf_bytes(assignment_id) == pdf
    assert storage.download_manifest_from_gcs(assignment_id) == b'{"assignment_id":"fixture"}'
    payload, generation = storage.download_session_from_gcs(session_id, with_generation=True)
    assert payload == b'{"session_id":"fixture"}'
    assert generation is not None
    assert (local_storage / "assignments" / assignment_id / "assignment.pdf").exists()


def test_local_storage_rejects_traversal_and_symlink(local_storage):
    with pytest.raises(ValueError):
        storage.upload_pdf_to_gcs("../escape", b"%PDF")

    assignment_id = "550e8400-e29b-41d4-a716-446655440000"
    target = local_storage / "assignments" / assignment_id
    target.mkdir(parents=True)
    (target / "assignment.pdf").symlink_to(Path(__file__))
    with pytest.raises(RuntimeError):
        storage.download_pdf_bytes(assignment_id)


def test_local_session_generation_conflict_is_detected(local_storage):
    session_id = "550e8400-e29b-41d4-a716-446655440001"
    _, generation = storage.upload_session_to_gcs(session_id, b"one", return_generation=True)
    with pytest.raises(storage.StorageConflict):
        storage.upload_session_to_gcs(session_id, b"two", if_generation_match=generation + 1)


def test_delete_assignment_removes_registered_sessions(local_storage):
    assignment_id = "550e8400-e29b-41d4-a716-446655440000"
    session_id = "550e8400-e29b-41d4-a716-446655440099"
    storage.upload_pdf_to_gcs(assignment_id, b"%PDF-1.4\nfixture")
    storage.upload_session_to_gcs(session_id, b'{"session_id":"fixture"}')
    storage.register_assignment_session(assignment_id, session_id)
    assert session_id in storage.list_assignment_session_ids(assignment_id)

    storage.delete_assignment_and_sessions(assignment_id)

    assert storage.list_assignment_session_ids(assignment_id) == []
    with pytest.raises(ValueError):
        storage.download_session_from_gcs(session_id)
    with pytest.raises(ValueError):
        storage.download_pdf_bytes(assignment_id)
