"""Schema helper tests."""
import pytest
from fastapi import HTTPException

from schemas import ConversationItem, Speaker, trim_conversation, validate_export_answers


def test_trim_conversation_noop_when_under_limit():
    items = [ConversationItem(speaker=Speaker.user, text="hi")]
    assert trim_conversation(items, max_turns=5) == items


def test_validate_export_answers_rejects_non_list():
    with pytest.raises(HTTPException) as exc:
        validate_export_answers({})
    assert exc.value.status_code == 400
    assert exc.value.detail == "answers must be a list"


def test_validate_export_answers_rejects_non_object_entry():
    with pytest.raises(HTTPException) as exc:
        validate_export_answers(["bad"])
    assert exc.value.status_code == 400
    assert "must be an object" in exc.value.detail


def test_validate_export_answers_accepts_null_answer_text():
    result = validate_export_answers([{"question_id": 2, "answer_text": None}])
    assert result == [{"question_id": 2, "answer_text": ""}]
