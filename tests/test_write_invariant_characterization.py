"""Characterization tests for write contract and parser fallback behavior."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import config
import gemini_service
import main as main_module
import session_service
from tests.conftest import TEST_ASSIGNMENT_ID


@pytest.fixture
def write_client(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: ("Mock", [{"id": 1, "text": "Q?"}]),
    )
    monkeypatch.setattr(gemini_service, "get_api_key", lambda: "test-api-key-not-used")
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)

    class FakeChunk:
        __slots__ = ("text",)

        def __init__(self, text: str):
            self.text = text

    class FakeModels:
        async def generate_content_stream(self, model, contents):
            async def _stream():
                yield FakeChunk("formatted")

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


def test_write_rejects_empty_candidate_when_contract_enforced(write_client, monkeypatch):
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", True)
    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [],
            "answer_candidate": "",
        },
    )
    assert response.status_code == 400
    assert "non-empty" in response.json()["detail"]


def test_write_rejects_missing_write_token_when_contract_enforced(write_client, monkeypatch):
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", True)
    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [{"speaker": "user", "text": "My answer is 5"}],
            "answer_candidate": "5",
        },
    )
    assert response.status_code == 403


def test_write_prompt_requires_confirmed_candidate_text():
    prompt = gemini_service.build_write_prompt("Title\n\nQuestion 1: Q", [], 1, "42")
    assert "confirmed answer" in prompt.lower()
    assert '"42"' in prompt
    assert "do not invent" in prompt.lower()


def test_parser_unsupported_layout_has_no_fallback_question(tmp_pdf_no_questions):
    from parser import parse_pdf_with_diagnostics

    _title, questions, warnings, status = parse_pdf_with_diagnostics(tmp_pdf_no_questions)
    assert questions == []
    assert status == "unsupported_layout"
    assert "unsupported_layout" in warnings


def test_session_confirm_issues_write_token(monkeypatch, write_client):
    monkeypatch.setattr(config, "ENFORCE_WRITE_CONTRACT", True)
    created = {
        "blob": {
            "session_id": "550e8400-e29b-41d4-a716-446655440001",
            "assignment_id": TEST_ASSIGNMENT_ID,
            "session_secret_hash": session_service._secret_digest("secret-abc"),
            "expires_at": "2099-01-01T00:00:00+00:00",
            "questions": {"1": {}},
        }
    }

    def fake_create(assignment_id, question_ids):
        return {
            "session_id": created["blob"]["session_id"],
            "session_secret": "secret-abc",
            "expires_at": created["blob"]["expires_at"],
        }

    def fake_load(session_id):
        from session_service import SessionState

        return SessionState(created["blob"])

    def fake_save(state):
        created["blob"] = state.data

    monkeypatch.setattr(session_service, "create_session", fake_create)
    monkeypatch.setattr(session_service, "load_session", fake_load)
    monkeypatch.setattr(session_service, "save_session", fake_save)

    confirm = write_client.post(
        "/api/session/550e8400-e29b-41d4-a716-446655440001/confirm",
        json={
            "session_secret": "secret-abc",
            "question_id": 1,
            "answer_text": "My final answer is 7",
        },
    )
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["confirmed"] is True
    assert body["write_token"]
