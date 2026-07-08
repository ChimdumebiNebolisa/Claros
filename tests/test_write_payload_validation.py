"""Write payload schema validation tests."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
from schemas import MAX_CONVERSATION_TURNS, MAX_MESSAGE_CHARS
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def fake_assignment(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: ("Mock", [{"id": 1, "text": "Q?"}]),
    )


def test_write_rejects_unknown_speaker():
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [{"speaker": "assistant", "text": "Hello"}],
            "answer_candidate": "",
        },
    )
    assert response.status_code == 422


def test_write_rejects_oversized_message_text():
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [{"speaker": "user", "text": "x" * (MAX_MESSAGE_CHARS + 1)}],
            "answer_candidate": "",
        },
    )
    assert response.status_code == 422


def test_write_rejects_excessive_conversation_turns():
    turns = [{"speaker": "user", "text": "hi"} for _ in range(MAX_CONVERSATION_TURNS + 1)]
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": turns,
            "answer_candidate": "",
        },
    )
    assert response.status_code == 422
