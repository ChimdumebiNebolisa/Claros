"""Session API tests with mocked GCS session storage."""
import json
import pytest
from fastapi.testclient import TestClient

import assignment_service
import config
import gemini_service
import main as main_module
import session_service
from tests.conftest import TEST_ASSIGNMENT_ID

_STORE: dict[str, bytes] = {}


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
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: ("Mock", [{"id": 1, "text": "Q1"}, {"id": 2, "text": "Q2"}]),
    )


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
    assert len(body["questions"]) == 2


def test_session_secret_is_keyed_hash_at_rest(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    stored = json.loads(next(iter(_STORE.values())))
    assert stored["session_secret_hash"]
    assert stored["session_secret_hash"] != start["session_secret"]
    assert "session_secret" not in stored


def test_restore_rejects_wrong_session_secret(client):
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    response = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": "wrong-secret"},
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
            "question_id": 1,
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
            "question_id": 1,
            "answer_text": "Photosynthesis",
        },
    )
    assert confirm.status_code == 200
    token = confirm.json()["write_token"]

    restore = client.post(
        f"/api/session/{start['session_id']}/restore",
        json={"session_secret": start["session_secret"]},
    )
    assert restore.status_code == 200
    assert restore.json()["questions"]["1"]["confirmed"] is True
    assert token


def test_write_token_single_use(client, monkeypatch):
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", True)
    monkeypatch.setattr(gemini_service, "get_api_key", lambda: "k")

    class FakeChunk:
        def __init__(self, text="ok"):
            self.text = text

    class FakeModels:
        async def generate_content_stream(self, model, contents):
            async def _stream():
                yield FakeChunk("ok")

            return _stream()

    class FakeAio:
        def __init__(self):
            self.models = FakeModels()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.aio = FakeAio()

    import types as std_types

    monkeypatch.setattr(gemini_service, "genai", std_types.SimpleNamespace(Client=FakeClient))

    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirm = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "question_id": 1,
            "answer_text": "42",
        },
    ).json()
    payload = {
        "question_id": 1,
        "conversation": [{"speaker": "user", "text": "forty two"}],
        "answer_candidate": "42",
        "write_token": confirm["write_token"],
        "session_id": start["session_id"],
        "session_secret": start["session_secret"],
    }
    first = client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert first.status_code == 200
    second = client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert second.status_code == 403
