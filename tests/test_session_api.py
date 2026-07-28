"""Session API tests with mocked GCS session storage."""
import json
import pytest
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
import storage
from manifest import build_manifest
from tests.conftest import TEST_ASSIGNMENT_ID

_STORE: dict[str, bytes] = {}
_TASK_ONE_ID = "task-q1"
_TASK_ONE_REGION_ID = f"{_TASK_ONE_ID}:side-panel"
_TASK_TWO_ID = "task-q2"


def _mock_manifest():
    return build_manifest(
        TEST_ASSIGNMENT_ID,
        "Mock",
        questions=[
            {
                "id": 1,
                "task_id": _TASK_ONE_ID,
                "text": "Q1",
                "answer_region": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.1},
                "approved": True,
                "needs_layout_review": False,
            },
            {
                "id": 2,
                "task_id": _TASK_TWO_ID,
                "text": "Q2",
                "answer_region": {"x": 0.1, "y": 0.4, "width": 0.4, "height": 0.1},
                "approved": True,
                "needs_layout_review": False,
            },
        ],
    )


@pytest.fixture(autouse=True)
def mock_session_storage(monkeypatch):
    _STORE.clear()

    def upload(session_id, payload):
        _STORE[session_id] = payload
        return f"gs://bucket/sessions/{session_id}.json"

    def download(session_id):
        if session_id not in _STORE:
            raise ValueError("missing")
        return _STORE[session_id]

    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", upload)
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", download)
    monkeypatch.setattr(session_service.storage, "register_assignment_session", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(session_service.storage, "delete_session_from_gcs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_manifest",
        lambda _id: _mock_manifest(),
    )
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_session_start_returns_credentials(client):
    response = client.post(
        "/api/session/start",
        json={"assignment_id": TEST_ASSIGNMENT_ID},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["session_secret"]
    assert [task["id"] for task in body["document"]["tasks"]] == [_TASK_ONE_ID, _TASK_TWO_ID]


def test_session_secret_is_keyed_hash_at_rest(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    stored = json.loads(next(iter(_STORE.values())))
    assert stored["session_secret_hash"]
    assert stored["session_secret_hash"] != start["session_secret"]
    assert "session_secret" not in stored
    assert _TASK_ONE_ID in stored["tasks"]


def test_legacy_plaintext_session_secret_cannot_authenticate():
    state = session_service.SessionState(
        {
            "session_id": "legacy",
            "assignment_id": TEST_ASSIGNMENT_ID,
            "session_secret": "legacy-plaintext-secret",
            "questions": {},
        }
    )
    assert state.verify_session_secret("legacy-plaintext-secret") is False


def test_restore_rejects_wrong_session_secret(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    response = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": "wrong-secret", "assignment_id": TEST_ASSIGNMENT_ID},
    )
    assert response.status_code == 403


def test_expired_session_is_deleted_on_access(monkeypatch):
    deleted = []
    monkeypatch.setattr(
        session_service.storage,
        "download_session_from_gcs",
        lambda _id: json.dumps(
            {
                "session_id": "expired-session",
                "assignment_id": TEST_ASSIGNMENT_ID,
                "session_secret_hash": "hash",
                "expires_at": "2020-01-01T00:00:00+00:00",
                "questions": {},
            }
        ).encode("utf-8"),
    )
    monkeypatch.setattr(session_service.storage, "delete_session_from_gcs", lambda session_id: deleted.append(session_id))

    with pytest.raises(Exception) as exc:
        session_service.load_session("expired-session")

    assert exc.value.status_code == 410
    assert deleted == ["expired-session"]


def test_confirm_requires_nonempty_answer(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    response = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "   ",
        },
    )
    assert response.status_code == 400


def test_confirm_and_restore_round_trip(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirm = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "Photosynthesis",
        },
    )
    assert confirm.status_code == 200
    token = confirm.json()["write_token"]

    restore = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": start["session_secret"], "assignment_id": TEST_ASSIGNMENT_ID},
    )
    assert restore.status_code == 200
    restored = restore.json()["responses"][_TASK_ONE_REGION_ID]
    assert restored["confirmed"] is True
    assert restored["confirmed_answer"] == "Photosynthesis"
    assert restored["write_token"]
    assert restored["write_token"] != token
    assert token


def test_write_token_replay_is_idempotent_after_success(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirm = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "42",
        },
    ).json()
    payload = {
        "task_id": _TASK_ONE_ID,
        "response_region_id": _TASK_ONE_REGION_ID,
        "conversation": [{"speaker": "user", "text": "forty two"}],
        "answer_candidate": "42",
        "write_token": confirm["write_token"],
        "session_id": start["session_id"],
        "session_secret": start["session_secret"],
    }
    first = client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert first.status_code == 200
    # Safe client retries after a successful write must not strand the student.
    second = client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert second.status_code == 200


def test_restore_reissues_write_token_for_confirmed_unwritten_answer(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirm = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "Leaf",
        },
    ).json()
    original_token = confirm["write_token"]

    restore = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": start["session_secret"], "assignment_id": TEST_ASSIGNMENT_ID},
    ).json()
    restored_token = restore["responses"][_TASK_ONE_REGION_ID]["write_token"]
    assert restored_token
    assert restored_token != original_token

    stale = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "conversation": [],
            "answer_candidate": "Leaf",
            "write_token": original_token,
            "session_id": start["session_id"],
            "session_secret": start["session_secret"],
        },
    )
    assert stale.status_code == 403

    fresh = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "conversation": [],
            "answer_candidate": "Leaf",
            "write_token": restored_token,
            "session_id": start["session_id"],
            "session_secret": start["session_secret"],
        },
    )
    assert fresh.status_code == 200


def test_reauthorize_write_endpoint_issues_fresh_token(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "Stem",
        },
    )
    reauth = client.post(
        f"/api/session/{start['session_id']}/reauthorize-write",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
        },
    )
    assert reauth.status_code == 200
    body = reauth.json()
    assert body["confirmed"] is True
    assert body["written"] is False
    assert body["write_token"]
    assert body["answer_text"] == "Stem"


def test_reconfirm_clears_previous_written_answer(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    first = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "Old",
        },
    ).json()
    assert (
        client.post(
            f"/api/write/{TEST_ASSIGNMENT_ID}",
            json={
                "task_id": _TASK_ONE_ID,
                "response_region_id": _TASK_ONE_REGION_ID,
                "conversation": [],
                "answer_candidate": "Old",
                "write_token": first["write_token"],
                "session_id": start["session_id"],
                "session_secret": start["session_secret"],
            },
        ).status_code
        == 200
    )

    second = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "New",
        },
    )
    assert second.status_code == 200
    assert second.json()["write_token"]

    restore = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": start["session_secret"], "assignment_id": TEST_ASSIGNMENT_ID},
    ).json()
    restored = restore["responses"][_TASK_ONE_REGION_ID]
    assert restored["confirmed_answer"] == "New"
    assert restored["written_answer"] == ""
    assert restored["written"] is False
    assert restored["write_token"]

    # Export must not resurrect the stale written answer.
    export_answers = session_service.written_answers_for_export(
        start["session_id"],
        start["session_secret"],
        TEST_ASSIGNMENT_ID,
        [],
    )
    assert export_answers == []


def test_create_session_fails_closed_when_registration_fails(monkeypatch, client):
    monkeypatch.setattr(
        session_service.storage,
        "register_assignment_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("register failed")),
    )
    deleted = []

    def delete_session(session_id):
        deleted.append(session_id)
        _STORE.pop(session_id, None)

    monkeypatch.setattr(session_service.storage, "delete_session_from_gcs", delete_session)
    response = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})
    assert response.status_code == 500
    assert deleted
    assert _STORE == {}


def test_restore_retries_after_storage_conflict(monkeypatch, client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ONE_ID,
            "response_region_id": _TASK_ONE_REGION_ID,
            "answer_text": "Retry",
        },
    )
    calls = {"count": 0}
    original_save = session_service.save_session

    def flaky_save(state):
        calls["count"] += 1
        if calls["count"] == 1:
            raise storage.StorageConflict("conflict")
        return original_save(state)

    monkeypatch.setattr(session_service, "save_session", flaky_save)
    restore = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": start["session_secret"], "assignment_id": TEST_ASSIGNMENT_ID},
    )
    assert restore.status_code == 200
    assert restore.json()["responses"][_TASK_ONE_REGION_ID]["write_token"]
    assert calls["count"] >= 2
