"""Gemini ephemeral token, write streaming, and optional debug helpers."""
import datetime
import logging
import re

from google import genai
from google.genai import types

import assignment_service
from agent import build_system_prompt
from config import LIVE_MODEL, get_api_key, get_text_model
from observability import record_metric

logger = logging.getLogger(__name__)


def create_session_config(assignment_id: str) -> dict:
    """Return ephemeral token + system prompt + model for browser-side Gemini Live."""
    title, questions = assignment_service.load_assignment_from_gcs(assignment_id)
    assignment_text = assignment_service.format_assignment_text(title, questions)
    system_prompt = build_system_prompt(assignment_text)
    api_key = get_api_key()
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1alpha"))
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        token = client.auth_tokens.create(
            config=types.CreateAuthTokenConfig(
                uses=1,
                expire_time=now_utc + datetime.timedelta(minutes=30),
                new_session_expire_time=now_utc + datetime.timedelta(minutes=2),
                http_options=types.HttpOptions(api_version="v1alpha"),
            )
        )
        token_value = token.name if token and getattr(token, "name", None) else None
    except Exception:
        record_metric("provider_failure", status="error", reason="provider")
        logger.exception("Ephemeral token creation failed for assignment %s", assignment_id)
        raise RuntimeError("Ephemeral token creation failed")
    if not token_value:
        raise RuntimeError("No token returned")
    return {
        "token": token_value,
        "model": LIVE_MODEL,
        "system_prompt": system_prompt,
        "title": title,
        "questions": questions,
    }


def build_write_prompt(
    assignment_text: str,
    conversation: list[dict],
    question_id: int,
    answer_candidate: str,
) -> str:
    candidate = (answer_candidate or "").strip()
    conv_str = "\n".join(
        f"{'User' if c.get('speaker') == 'user' else 'Claros'}: {c.get('text', '')}"
        for c in (conversation or [])
    )
    return f"""You are formatting a student's confirmed answer for their worksheet.

Assignment:
{assignment_text}

Conversation context (for reference only; do not invent new content):
{conv_str}

The student has confirmed their final answer for Question {question_id} as:
"{candidate}"

Rewrite ONLY this confirmed answer as plain text suitable for the answer box.
- Do not change the meaning.
- Do not add facts, steps, or content that are not already implied by the confirmed answer.
- Do not include the question number, labels, or preamble.
- Use plain text only (no LaTeX or markdown delimiters).
Output only the answer text."""


async def stamp_confirmed_answer(answer_candidate: str):
    """Yield the confirmed answer text without calling Gemini."""
    text = re.sub(r"\$([^$]+)\$", r"\1", (answer_candidate or "").strip())
    if text:
        yield text


async def stream_write_answer(
    assignment_id: str,
    question_id: int,
    conversation: list[dict],
    answer_candidate: str,
):
    """Async generator that streams generated answer text for a question."""
    title, questions = assignment_service.load_assignment_from_gcs(assignment_id)
    assignment_text = assignment_service.format_assignment_text(title, questions)
    prompt = build_write_prompt(assignment_text, conversation, question_id, answer_candidate)
    api_key = get_api_key()
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1alpha"))
    text_model = get_text_model()
    candidate = answer_candidate or ""
    candidate_empty = not bool(candidate.strip())
    logger.info(
        "[write-chain] assignment=%s question_id=%s candidate_empty=%s",
        assignment_id,
        question_id,
        candidate_empty,
    )
    chunk_count = 0
    try:
        stream = await client.aio.models.generate_content_stream(
            model=text_model,
            contents=prompt,
        )
        async for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                text = re.sub(r"\$([^$]+)\$", r"\1", text)
                chunk_count += 1
                if chunk_count == 1:
                    logger.info("[write-chain] first chunk sent len=%s", len(text))
                yield text
        logger.info("[write-chain] stream finished total_chunks=%s", chunk_count)
    except Exception:
        record_metric("provider_failure", status="error", reason="provider")
        logger.exception("stream_write failed for assignment %s question %s", assignment_id, question_id)
        yield "\n[Error: Answer generation failed. Please try again.]"


async def debug_gemini_text_call() -> dict:
    """Verify backend can reach Gemini text API. For local diagnostics only."""
    api_key = get_api_key()
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1alpha"))
    text_model = get_text_model()
    logger.info("[debug-gemini] Attempting text call with model=%r", text_model)
    response = await client.aio.models.generate_content(
        model=text_model,
        contents="Reply with exactly one word: ok",
    )
    result_text = response.text.strip() if response.text else "(empty)"
    logger.info("[debug-gemini] SUCCESS response_chars=%s", len(result_text))
    return {"status": "ok", "model": text_model, "response": result_text}
