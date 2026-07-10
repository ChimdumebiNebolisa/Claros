"""Request/response schemas and validation helpers."""
from enum import Enum

from fastapi import HTTPException
from pydantic import BaseModel, Field

import config

MAX_MESSAGE_CHARS = 8000
MAX_ANSWER_CANDIDATE_CHARS = 8000


class Speaker(str, Enum):
    user = "user"
    claros = "claros"


class ConversationItem(BaseModel):
    speaker: Speaker
    text: str = Field(default="", max_length=MAX_MESSAGE_CHARS)


class WriteRequest(BaseModel):
    question_id: int
    conversation: list[ConversationItem] = Field(
        default_factory=list,
        max_length=config.MAX_CONVERSATION_TURNS,
    )
    answer_candidate: str = Field(default="", max_length=MAX_ANSWER_CANDIDATE_CHARS)
    write_token: str = Field(default="", max_length=2048)
    session_id: str = Field(default="", max_length=64)
    session_secret: str = Field(default="", max_length=128)


class SessionStartRequest(BaseModel):
    assignment_id: str


class SessionConfirmRequest(BaseModel):
    session_secret: str = Field(min_length=8, max_length=128)
    question_id: int
    answer_text: str = Field(min_length=1, max_length=MAX_ANSWER_CANDIDATE_CHARS)


class SessionRestoreRequest(BaseModel):
    session_secret: str = Field(min_length=8, max_length=128)


class ExportRequest(BaseModel):
    answers: list[dict]


def trim_conversation(
    items: list[ConversationItem],
    max_turns: int | None = None,
) -> list[ConversationItem]:
    """Keep the most recent turns when conversation history exceeds the soft limit."""
    limit = max_turns if max_turns is not None else config.CONVERSATION_TRIM_TURNS
    if len(items) <= limit:
        return items
    return items[-limit:]


def validate_export_answers(raw_answers) -> list[dict]:
    if not isinstance(raw_answers, list):
        raise HTTPException(status_code=400, detail="answers must be a list")

    answers = []
    for index, answer in enumerate(raw_answers):
        if not isinstance(answer, dict):
            raise HTTPException(status_code=400, detail=f"answers[{index}] must be an object")

        question_id = answer.get("question_id")
        if isinstance(question_id, bool) or not isinstance(question_id, int):
            raise HTTPException(
                status_code=400,
                detail=f"answers[{index}].question_id must be an integer",
            )
        if question_id < 1:
            raise HTTPException(
                status_code=400,
                detail=f"answers[{index}].question_id must be positive",
            )

        answer_text = answer.get("answer_text", "")
        if answer_text is None:
            answer_text = ""
        elif not isinstance(answer_text, str):
            raise HTTPException(
                status_code=400,
                detail=f"answers[{index}].answer_text must be a string",
            )

        answers.append({"question_id": question_id, "answer_text": answer_text})

    return answers
