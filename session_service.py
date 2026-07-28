"""Server-side tutoring session state and write-token issuance."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

import config
import storage
from manifest import AssignmentManifest
from observability import record_metric

logger = logging.getLogger(__name__)


class SessionState:
    """In-memory view of a persisted session blob."""

    def __init__(self, data: dict, storage_generation: int | None = None):
        self.data = data
        self.storage_generation = storage_generation

    @property
    def session_id(self) -> str:
        return self.data["session_id"]

    @property
    def assignment_id(self) -> str:
        return self.data["assignment_id"]

    @property
    def session_secret(self) -> str:
        """Legacy compatibility accessor; plaintext session records are invalid."""
        return ""

    def verify_session_secret(self, candidate: str) -> bool:
        """Verify a client secret without exposing or persisting new plaintext secrets."""
        if not candidate:
            return False
        stored_hash = self.data.get("session_secret_hash")
        if not stored_hash:
            return False
        expected = _secret_digest(candidate)
        return hmac.compare_digest(stored_hash, expected)

    def get_question(self, question_id: int) -> dict | None:
        return self.data.get("questions", {}).get(str(question_id))

    def set_confirmed(self, question_id: int, answer_text: str) -> None:
        q = self.data.setdefault("questions", {}).setdefault(str(question_id), {})
        q["draft_answer"] = answer_text
        q["confirmed_answer"] = answer_text
        q["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        q["write_tokens_used"] = q.get("write_tokens_used", [])

    def is_confirmed(self, question_id: int) -> bool:
        q = self.get_question(question_id)
        return bool(q and q.get("confirmed_answer", "").strip())

    def confirmed_answer(self, question_id: int) -> str:
        q = self.get_question(question_id)
        return (q or {}).get("confirmed_answer", "")

    def mark_written(self, question_id: int, answer_text: str) -> None:
        q = self.data.setdefault("questions", {}).setdefault(str(question_id), {})
        if q.get("confirmed_answer", "") != answer_text:
            raise HTTPException(status_code=403, detail="answer_text does not match confirmed answer")
        q["written_answer"] = answer_text
        q["written_at"] = datetime.now(timezone.utc).isoformat()


def _session_expires_at() -> str:
    hours = config.SESSION_TTL_HOURS
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _task_snapshot(question: dict[str, Any]) -> str:
    """Fingerprint the task evidence that a confirmation is allowed to write into."""
    try:
        question_id = int(question["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Session task requires an integer id") from exc
    payload = {
        "id": question_id,
        "task_id": question.get("task_id"),
        "label": question.get("label"),
        "text": question.get("text", ""),
        "page": question.get("page"),
        "page_index": question.get("page_index"),
        "prompt_region": question.get("prompt_region"),
        "answer_region": question.get("answer_region"),
        "prompt_bbox": question.get("prompt_bbox"),
        "answer_bbox": question.get("answer_bbox"),
        "response_type": question.get("response_type"),
        "answer_region_status": question.get("answer_region_status"),
        "needs_layout_review": question.get("needs_layout_review"),
        "source_blocks": question.get("source_blocks", []),
        "approved": question.get("approved"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _session_questions(questions: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    session_questions: dict[str, dict[str, str]] = {}
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("Session questions must be objects")
        try:
            question_id = int(question["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Session task requires an integer id") from exc
        key = str(question_id)
        if key in session_questions:
            raise ValueError(f"Duplicate session question id: {question_id}")
        session_questions[key] = {"task_snapshot": _task_snapshot(question)}
    return session_questions


def create_session(assignment_id: str, questions: list[dict[str, Any]]) -> dict:
    session_id = str(uuid.uuid4())
    session_secret = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    blob = {
        "session_id": session_id,
        "assignment_id": assignment_id,
        "session_secret_hash": _secret_digest(session_secret),
        "session_secret_version": 1,
        "created_at": now,
        "expires_at": _session_expires_at(),
        "questions": _session_questions(questions),
        "metrics": {"errors_recovered": 0},
    }
    storage.upload_session_to_gcs(session_id, json.dumps(blob).encode("utf-8"))
    return {
        "session_id": session_id,
        "session_secret": session_secret,
        "expires_at": blob["expires_at"],
    }


def load_session(session_id: str) -> SessionState:
    try:
        try:
            downloaded = storage.download_session_from_gcs(session_id, with_generation=True)
        except TypeError as exc:
            if "unexpected keyword" not in str(exc):
                raise
            downloaded = storage.download_session_from_gcs(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    if isinstance(downloaded, tuple):
        raw, generation = downloaded
    else:
        raw, generation = downloaded, None
    data = json.loads(raw)
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                try:
                    storage.delete_session_from_gcs(session_id)
                except Exception:
                    logger.exception("Expired session cleanup failed")
                record_metric("session_expired", status="expired")
                raise HTTPException(status_code=410, detail="Session expired")
        except ValueError:
            pass
    return SessionState(data, storage_generation=generation)


def save_session(state: SessionState) -> None:
    payload = json.dumps(state.data).encode("utf-8")
    try:
        result = storage.upload_session_to_gcs(
            state.session_id,
            payload,
            if_generation_match=state.storage_generation,
            return_generation=True,
        )
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        result = storage.upload_session_to_gcs(state.session_id, payload)
    if isinstance(result, tuple):
        state.storage_generation = result[1]
    else:
        state.storage_generation = None


def _answer_fingerprint(answer_text: str) -> str:
    return hashlib.sha256(answer_text.encode("utf-8")).hexdigest()


def _hmac_secret() -> bytes:
    secret = config.get_session_hmac_secret()
    return secret.encode("utf-8")


def _secret_digest(session_secret: str) -> str:
    return hmac.new(_hmac_secret(), session_secret.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_write_token(
    state: SessionState,
    question_id: int,
    answer_text: str,
) -> str:
    if not answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text must be non-empty")
    if not state.is_confirmed(question_id):
        raise HTTPException(status_code=400, detail="Answer not confirmed for this question")
    confirmed = state.confirmed_answer(question_id)
    if confirmed != answer_text:
        raise HTTPException(status_code=400, detail="answer_text does not match confirmed answer")

    nonce = secrets.token_urlsafe(16)
    payload = f"{state.session_id}:{question_id}:{_answer_fingerprint(answer_text)}:{nonce}"
    sig = hmac.new(_hmac_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}:{sig}"

    q = state.data.setdefault("questions", {}).setdefault(str(question_id), {})
    used = q.setdefault("pending_write_tokens", [])
    used.append({"nonce": nonce, "issued_at": datetime.now(timezone.utc).isoformat()})
    save_session(state)
    return token


def validate_write_token(
    state: SessionState,
    question_id: int,
    answer_candidate: str,
    write_token: str,
) -> None:
    if not write_token:
        raise HTTPException(status_code=403, detail="write_token is required")
    if not answer_candidate.strip():
        raise HTTPException(status_code=400, detail="answer_candidate must be non-empty")

    parts = write_token.split(":")
    if len(parts) != 5:
        raise HTTPException(status_code=403, detail="Invalid write_token")
    sid, qid_str, fp, nonce, sig = parts
    try:
        token_question_id = int(qid_str)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid write_token") from exc
    if sid != state.session_id or token_question_id != question_id:
        raise HTTPException(status_code=403, detail="write_token does not match session or question")
    if fp != _answer_fingerprint(answer_candidate):
        raise HTTPException(status_code=403, detail="write_token does not match answer_candidate")

    payload = f"{sid}:{qid_str}:{fp}:{nonce}"
    expected = hmac.new(_hmac_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=403, detail="Invalid write_token signature")

    q = state.get_question(question_id) or {}
    pending = q.get("pending_write_tokens", [])
    if not any(item.get("nonce") == nonce for item in pending):
        raise HTTPException(status_code=403, detail="write_token already used or unknown")

    # Single-use: remove nonce after validation
    q["pending_write_tokens"] = [item for item in pending if item.get("nonce") != nonce]
    q.setdefault("write_tokens_used", []).append(nonce)
    save_session(state)


def validate_task_snapshot(state: SessionState, question_id: int, current_question: dict[str, Any]) -> None:
    question_state = state.get_question(question_id)
    expected = (question_state or {}).get("task_snapshot", "")
    if not expected or not hmac.compare_digest(expected, _task_snapshot(current_question)):
        raise HTTPException(status_code=409, detail="Task changed since confirmation. Reload the worksheet and confirm again.")


def mark_answer_written(
    state: SessionState,
    question_id: int,
    answer_text: str,
    current_question: dict[str, Any],
) -> None:
    validate_task_snapshot(state, question_id, current_question)
    state.mark_written(question_id, answer_text)
    save_session(state)


def written_answers_for_export(
    session_id: str,
    session_secret: str,
    assignment_id: str,
    current_questions: list[dict[str, Any]],
) -> list[dict]:
    state = load_session(session_id)
    if state.assignment_id != assignment_id:
        raise HTTPException(status_code=403, detail="Session does not match assignment")
    if not state.verify_session_secret(session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    current_by_id = {str(question.get("id")): question for question in current_questions}
    answers = []
    for question_id, data in state.data.get("questions", {}).items():
        if not str(data.get("written_answer", "")).strip():
            continue
        question = current_by_id.get(question_id)
        if question is None:
            raise HTTPException(status_code=409, detail="Task changed since writing. Reload the worksheet before export.")
        validate_task_snapshot(state, int(question_id), question)
        answers.append({"question_id": int(question_id), "answer_text": data["written_answer"]})
    return answers


def confirm_answer(
    session_id: str,
    session_secret: str,
    question_id: int,
    answer_text: str,
) -> dict:
    if not answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text must be non-empty")
    state = load_session(session_id)
    if not state.verify_session_secret(session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    if str(question_id) not in state.data.get("questions", {}):
        raise HTTPException(status_code=400, detail=f"Unknown question id: {question_id}")

    approved_text = answer_text
    state.set_confirmed(question_id, approved_text)
    save_session(state)
    write_token = issue_write_token(state, question_id, approved_text)
    return {
        "question_id": question_id,
        "confirmed": True,
        "write_token": write_token,
    }


def restore_session_for_client(session_id: str, session_secret: str) -> dict:
    state = load_session(session_id)
    if not state.verify_session_secret(session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    questions = {}
    for qid, qdata in state.data.get("questions", {}).items():
        questions[qid] = {
            "confirmed_answer": qdata.get("confirmed_answer", ""),
            "confirmed": bool(qdata.get("confirmed_answer", "").strip()),
        }
    return {
        "session_id": session_id,
        "assignment_id": state.assignment_id,
        "expires_at": state.data.get("expires_at"),
        "questions": questions,
    }


def init_question_ids_from_manifest(manifest: AssignmentManifest) -> list[int]:
    return [q.id for q in manifest.questions]
