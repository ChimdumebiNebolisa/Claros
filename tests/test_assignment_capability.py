"""Assignment owner-capability regression coverage."""
import json

from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
from manifest import build_manifest
from tests.conftest import TEST_ASSIGNMENT_ID


def _manifest(capability: str):
    return build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title="Capability test",
        questions=[{"id": 1, "text": "Question", "answer_region": {"x": 0.1, "y": 0.1, "width": 0.4, "height": 0.1}}],
        assignment_capability_hash=assignment_service.assignment_capability_digest(capability),
    )


def test_sensitive_routes_reject_missing_or_wrong_assignment_capability(monkeypatch):
    capability = "owner-capability"
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: _manifest(capability))
    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", lambda _id: ("Capability test", [{"id": 1, "text": "Question"}]))
    client = TestClient(main_module.app)

    missing = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})
    wrong = client.post(
        "/api/session/start",
        headers={"X-Assignment-Capability": "wrong"},
        json={"assignment_id": TEST_ASSIGNMENT_ID},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403


def test_capability_authorizes_session_but_export_uses_only_written_server_answers(monkeypatch):
    capability = "owner-capability"
    stored = {}
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: _manifest(capability))
    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", lambda _id: ("Capability test", [{"id": 1, "text": "Question"}]))
    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", lambda sid, payload, **_kwargs: stored.setdefault(sid, payload))
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", lambda sid, **_kwargs: stored[sid])
    monkeypatch.setattr(session_service, "written_answers_for_export", lambda *_args: [{"question_id": 1, "answer_text": "written"}])
    monkeypatch.setattr(main_module, "build_export_response", lambda _id, answers: {"answers": answers})
    client = TestClient(main_module.app)
    headers = {"X-Assignment-Capability": capability}

    started = client.post("/api/session/start", headers=headers, json={"assignment_id": TEST_ASSIGNMENT_ID})
    assert started.status_code == 200

    bypass = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session", "session_secret": "session-secret"},
    )
    injected = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        headers=headers,
        json={"session_id": "session", "session_secret": "session-secret", "answers": [{"question_id": 1, "answer_text": "injected"}]},
    )
    authorized = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        headers=headers,
        json={"session_id": "session", "session_secret": "session-secret"},
    )

    assert bypass.status_code == 403
    assert injected.status_code == 422
    assert authorized.status_code == 200
    assert authorized.json() == {"answers": [{"question_id": 1, "answer_text": "written"}]}


def test_written_answer_is_persisted_in_session_state(monkeypatch):
    stored = {}

    def upload(session_id, payload, **_kwargs):
        stored[session_id] = payload

    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", upload)
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", lambda sid, **_kwargs: stored[sid])

    created = session_service.create_session(TEST_ASSIGNMENT_ID, [1])
    state = session_service.load_session(created["session_id"])
    state.set_confirmed(1, "Student answer")
    session_service.save_session(state)
    session_service.mark_answer_written(state, 1, "Student answer")

    restored = json.loads(stored[created["session_id"]])
    assert restored["questions"]["1"]["written_answer"] == "Student answer"
