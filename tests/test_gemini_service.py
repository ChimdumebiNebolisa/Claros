"""Gemini service unit tests (no real API calls)."""
import asyncio
import types

import gemini_service


def test_build_write_prompt_includes_assignment_and_question():
    prompt = gemini_service.build_write_prompt(
        "Question 1: What is 2+2?",
        [{"speaker": "user", "text": "I think it is 4."}],
        question_id=1,
        answer_candidate="4",
    )
    assert "Question 1: What is 2+2?" in prompt
    assert "User: I think it is 4." in prompt
    assert "Question 1" in prompt
    assert 'The student stated their answer as: "4"' in prompt


def test_build_write_prompt_omits_candidate_line_when_empty():
    prompt = gemini_service.build_write_prompt(
        "Assignment",
        [],
        question_id=2,
        answer_candidate="",
    )
    assert "The student stated their answer as" not in prompt


def test_stream_write_answer_yields_error_text_on_generation_failure(monkeypatch):
    monkeypatch.setattr(
        gemini_service.assignment_service,
        "load_assignment_from_gcs",
        lambda _id: ("Title", [{"id": 1, "text": "Q?"}]),
    )
    monkeypatch.setattr(gemini_service, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(gemini_service, "get_text_model", lambda: "gemini-test")

    class FakeModels:
        async def generate_content_stream(self, model, contents):
            raise RuntimeError("generation failed")

    class FakeAio:
        def __init__(self):
            self.models = FakeModels()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.aio = FakeAio()

    monkeypatch.setattr(
        gemini_service,
        "genai",
        types.SimpleNamespace(Client=FakeClient),
    )

    async def collect():
        chunks = []
        async for piece in gemini_service.stream_write_answer(
            "550e8400-e29b-41d4-a716-446655440000", 1, [], ""
        ):
            chunks.append(piece)
        return chunks

    chunks = asyncio.run(collect())
    assert any("Error" in piece for piece in chunks)
