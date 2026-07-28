"""Gemini ephemeral token and optional debug helpers."""
import datetime
import logging

from google import genai
from google.genai import types

import assignment_service
from agent import build_system_prompt
from config import LIVE_MODEL, get_api_key, get_text_model
from observability import record_metric

logger = logging.getLogger(__name__)


def create_session_config(assignment_id: str) -> dict:
    """Return ephemeral token + system prompt + model for browser-side Gemini Live."""
    manifest = assignment_service.load_assignment_manifest_for_client(assignment_id)
    title = manifest.title
    questions = manifest.to_questions_dict(approved_only=manifest.review_mode == "teacher")
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


async def stamp_confirmed_answer(answer_candidate: str):
    """Yield the exact server-authorized answer without model transformation."""
    if answer_candidate:
        yield answer_candidate


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
