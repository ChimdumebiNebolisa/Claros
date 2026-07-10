"""POST /api/write tests with mocked GCS and Gemini (no real API calls)."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import config
import gemini_service
import main as main_module
import session_service
from tests.conftest import TEST_ASSIGNMENT_ID

_FIXED_TITLE = "Mock Assignment"
_FIXED_QUESTIONS = [
    {"id": 1, "text": "First?"},
    {"id": 3, "text": "Second?"},
    {"id": 7, "text": "Third?"},
]

_STORE: dict[str, bytes] = {}


def _fake_load_assignment(_assignment_id: str):
    return _FIXED_TITLE, list(_FIXED_QUESTIONS)


@pytest.fixture
def write_client(monkeypatch):
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
    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", _fake_load_assignment)
    monkeypatch.setattr(gemini_service, "get_api_key", lambda: "test-api-key-not-used")
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", True)

    class FakeChunk:
        __slots__ = ("text",)

        def __init__(self, text: str):
            self.text = text

    class FakeModels:
        async def generate_content_stream(self, model, contents):
            async def _stream():
                yield FakeChunk("stub-")
                yield FakeChunk("answer")

            return _stream()

    class FakeAio:
        def __init__(self):
            self.models = FakeModels()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.aio = FakeAio()

    import types as std_types

    monkeypatch.setattr(gemini_service, "genai", std_types.SimpleNamespace(Client=FakeClient))
    return TestClient(main_module.app)


def _confirmed_write_payload(client: TestClient) -> dict:
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirm = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "question_id": 7,
            "answer_text": "7",
        },
    ).json()
    return {
        "question_id": 7,
        "conversation": [{"speaker": "user", "text": "My answer is seven."}],
        "answer_candidate": "7",
        "write_token": confirm["write_token"],
        "session_id": start["session_id"],
        "session_secret": start["session_secret"],
    }


def test_write_unknown_question_id_returns_400(write_client: TestClient, monkeypatch):
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", False)
    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 99,
            "conversation": [],
            "answer_candidate": "x",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "Unknown question id" in body["detail"]


def test_write_valid_question_id_streams_stub_text(write_client: TestClient):
    payload = _confirmed_write_payload(write_client)
    response = write_client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert response.text == "stub-answer"
