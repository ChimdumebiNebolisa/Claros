"""Request/response schemas and validation helpers."""
from enum import Enum

from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict

import config
from manifest import normalize_bbox

MAX_MESSAGE_CHARS = 8000
MAX_ANSWER_CANDIDATE_CHARS = 8000
MAX_EXPORT_ANSWER_CHARS = 4000
MAX_LAYOUT_OVERRIDES = 100


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


class LayoutOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: int = Field(ge=1)
    page_index: int = Field(ge=0)
    answer_bbox: list[float]


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[dict]
    layout_overrides: list[LayoutOverride] = Field(default_factory=list, max_length=MAX_LAYOUT_OVERRIDES)


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
        if len(answer_text) > MAX_EXPORT_ANSWER_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"answers[{index}].answer_text exceeds maximum length",
            )

        answers.append({"question_id": question_id, "answer_text": answer_text})

    return answers


def validate_layout_overrides(raw_overrides) -> list[dict]:
    if raw_overrides is None:
        return []
    if not isinstance(raw_overrides, list):
        raise HTTPException(status_code=400, detail="layout_overrides must be a list")
    if len(raw_overrides) > MAX_LAYOUT_OVERRIDES:
        raise HTTPException(status_code=400, detail="too many layout_overrides")

    seen: set[int] = set()
    overrides: list[dict] = []
    for index, item in enumerate(raw_overrides):
        if isinstance(item, LayoutOverride):
            payload = item.model_dump()
        elif isinstance(item, dict):
            try:
                payload = LayoutOverride.model_validate(item).model_dump()
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"layout_overrides[{index}] is invalid: {exc}",
                ) from exc
        else:
            raise HTTPException(status_code=400, detail=f"layout_overrides[{index}] must be an object")

        qid = payload["question_id"]
        if qid in seen:
            raise HTTPException(status_code=400, detail=f"duplicate layout override for question_id {qid}")
        seen.add(qid)
        try:
            payload["answer_bbox"] = normalize_bbox(payload["answer_bbox"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"layout_overrides[{index}].answer_bbox: {exc}") from exc
        overrides.append(payload)
    return overrides
