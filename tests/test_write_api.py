"""POST /api/write tests with mocked GCS and Gemini (no real API calls)."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
from manifest import build_manifest
from tests.conftest import TEST_ASSIGNMENT_ID

_FIXED_TITLE = "Mock Assignment"
_FIXED_QUESTIONS = [
    {"id": 1, "task_id": "task-first", "text": "First?", "answer_region": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.1}, "approved": True, "needs_layout_review": False},
    {"id": 3, "task_id": "task-second", "text": "Second?", "answer_region": {"x": 0.1, "y": 0.4, "width": 0.4, "height": 0.1}, "approved": True, "needs_layout_review": False},
    {"id": 7, "task_id": "task-third", "text": "Third?", "answer_region": {"x": 0.1, "y": 0.6, "width": 0.4, "height": 0.1}, "approved": True, "needs_layout_review": False},
]
_TASK_ID = "task-third"
_RESPONSE_REGION_ID = f"{_TASK_ID}:side-panel"

_STORE: dict[str, bytes] = {}


def _fake_manifest(_assignment_id: str, questions: list[dict] | None = None):
    return build_manifest(
        TEST_ASSIGNMENT_ID,
        _FIXED_TITLE,
        questions=list(_FIXED_QUESTIONS if questions is None else questions),
    )


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
    monkeypatch.setattr(session_service.storage, "register_assignment_session", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(session_service.storage, "delete_session_from_gcs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", _fake_manifest)
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)
    return TestClient(main_module.app)


def _confirmed_write_payload(client: TestClient) -> dict:
    start = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirm = client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ID,
            "response_region_id": _RESPONSE_REGION_ID,
            "answer_text": "7",
        },
    ).json()
    return {
        "task_id": _TASK_ID,
        "response_region_id": _RESPONSE_REGION_ID,
        "conversation": [{"speaker": "user", "text": "My answer is seven."}],
        "answer_candidate": "7",
        "write_token": confirm["write_token"],
        "session_id": start["session_id"],
        "session_secret": start["session_secret"],
    }


def test_write_unknown_task_id_returns_400(write_client: TestClient):
    payload = _confirmed_write_payload(write_client)
    payload["task_id"] = "task-missing"
    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json=payload,
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "Unknown task_id" in body["detail"]


def test_write_valid_task_id_streams_stub_text(write_client: TestClient):
    payload = _confirmed_write_payload(write_client)
    response = write_client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    # Contract-valid writes stamp the confirmed candidate without Gemini.
    assert response.text == "7"


def test_write_rejects_any_change_to_the_confirmed_answer_without_consuming_its_token(write_client: TestClient):
    payload = _confirmed_write_payload(write_client)
    payload["answer_candidate"] = "Case Sensitive"
    start = write_client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirmation = write_client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ID,
            "response_region_id": _RESPONSE_REGION_ID,
            "answer_text": "Case Sensitive",
        },
    ).json()
    payload.update(
        write_token=confirmation["write_token"],
        session_id=start["session_id"],
        session_secret=start["session_secret"],
    )

    for changed in ("case sensitive", "Case  Sensitive", "Case Sensitive\u03c0"):
        payload["answer_candidate"] = changed
        response = write_client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
        assert response.status_code == 403

    payload["answer_candidate"] = "Case Sensitive"
    response = write_client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert response.status_code == 200
    assert response.text == "Case Sensitive"


def test_write_preserves_the_full_confirmed_string_including_outer_whitespace(write_client: TestClient):
    answer = "  Case $x$  \u03c0  "
    start = write_client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID}).json()
    confirmation = write_client.post(
        f"/api/session/{start['session_id']}/confirm",
        json={
            "session_secret": start["session_secret"],
            "task_id": _TASK_ID,
            "response_region_id": _RESPONSE_REGION_ID,
            "answer_text": answer,
        },
    ).json()

    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "task_id": _TASK_ID,
            "response_region_id": _RESPONSE_REGION_ID,
            "answer_candidate": answer,
            "write_token": confirmation["write_token"],
            "session_id": start["session_id"],
            "session_secret": start["session_secret"],
        },
    )

    assert response.status_code == 200
    assert response.text == answer


def test_write_rejects_a_task_that_changed_after_confirmation(write_client: TestClient, monkeypatch):
    payload = _confirmed_write_payload(write_client)
    changed_questions = [dict(question) for question in _FIXED_QUESTIONS]
    changed_questions[2]["text"] = "A different task now has this numeric id."
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_manifest",
        lambda _id: _fake_manifest(_id, changed_questions),
    )

    response = write_client.post(f"/api/write/{TEST_ASSIGNMENT_ID}", json=payload)
    assert response.status_code == 409
    assert "Task changed since confirmation" in response.json()["detail"]
