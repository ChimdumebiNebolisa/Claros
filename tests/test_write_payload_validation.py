"""Write payload schema validation tests."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import config
import main as main_module
from schemas import MAX_MESSAGE_CHARS, Speaker, ConversationItem, trim_conversation
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


@pytest.fixture
def fake_assignment(monkeypatch):
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: (
            "Mock",
            [
                {
                    "id": 1,
                    "text": "Q?",
                    "answer_region": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.1},
                    "needs_layout_review": False,
                }
            ],
        ),
    )


def test_write_rejects_unknown_speaker(fake_assignment):
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [{"speaker": "assistant", "text": "Hello"}],
            "answer_candidate": "",
        },
    )
    assert response.status_code == 422


def test_write_rejects_oversized_message_text(fake_assignment):
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [{"speaker": "user", "text": "x" * (MAX_MESSAGE_CHARS + 1)}],
            "answer_candidate": "",
        },
    )
    assert response.status_code == 422


def test_write_rejects_absurdly_long_conversation(fake_assignment):
    turns = [{"speaker": "user", "text": "hi"} for _ in range(config.MAX_CONVERSATION_TURNS + 1)]
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": turns,
            "answer_candidate": "",
        },
    )
    assert response.status_code == 422


def test_trim_conversation_keeps_most_recent_turns():
    items = [ConversationItem(speaker=Speaker.user, text=str(i)) for i in range(10)]
    trimmed = trim_conversation(items, max_turns=3)
    assert len(trimmed) == 3
    assert [item.text for item in trimmed] == ["7", "8", "9"]


def test_write_accepts_long_conversation_and_trims(monkeypatch, fake_assignment):
    captured = {}

    def fake_stream(assignment_id, question_id, conversation, answer_candidate):
        captured["conversation"] = conversation

        async def _gen():
            yield "ok"

        return _gen()

    monkeypatch.setattr(main_module, "stream_write_answer", fake_stream)
    monkeypatch.setattr(main_module.config, "CONVERSATION_TRIM_TURNS", 50)
    monkeypatch.setattr(main_module.config, "ENFORCE_WRITE_CONTRACT", False)

    turns = [{"speaker": "user", "text": f"turn-{i}"} for i in range(120)]
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={"question_id": 1, "conversation": turns, "answer_candidate": "ok"},
    )
    assert response.status_code == 200
    assert len(captured["conversation"]) == 50
    assert captured["conversation"][-1]["text"] == "turn-119"
