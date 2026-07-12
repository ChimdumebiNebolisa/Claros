"""Server-side tutoring session state and write-token issuance."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

import config
import storage
from manifest import AssignmentManifest

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
        """Return a legacy plaintext secret when loading pre-hash sessions."""
        return self.data.get("session_secret", "")

    def verify_session_secret(self, candidate: str) -> bool:
        """Verify a client secret without exposing or persisting new plaintext secrets."""
        if not candidate:
            return False
        stored_hash = self.data.get("session_secret_hash")
        if stored_hash:
            expected = _secret_digest(candidate)
            return hmac.compare_digest(stored_hash, expected)
        # Compatibility for sessions created before keyed hashing was introduced.
        return bool(self.session_secret) and hmac.compare_digest(self.session_secret, candidate)

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


def _session_expires_at() -> str:
    hours = config.SESSION_TTL_HOURS
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def create_session(assignment_id: str, question_ids: list[int]) -> dict:
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
        "questions": {str(qid): {} for qid in question_ids},
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


def _normalize_answer(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _answer_fingerprint(answer_text: str) -> str:
    return hashlib.sha256(_normalize_answer(answer_text).encode("utf-8")).hexdigest()


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
    if _normalize_answer(confirmed) != _normalize_answer(answer_text):
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
    if sid != state.session_id or int(qid_str) != question_id:
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

    state.set_confirmed(question_id, answer_text.strip())
    save_session(state)
    write_token = issue_write_token(state, question_id, answer_text.strip())
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
