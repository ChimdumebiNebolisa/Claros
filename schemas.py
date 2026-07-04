"""Request/response schemas and validation helpers."""
from fastapi import HTTPException
from pydantic import BaseModel


class WriteRequest(BaseModel):
    question_id: int
    conversation: list[dict]
    answer_candidate: str = ""


class ExportRequest(BaseModel):
    answers: list[dict]


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
