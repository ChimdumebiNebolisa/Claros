"""Server-authoritative mutable response state for canonical document targets."""
from __future__ import annotations

import base64
import binascii
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

SESSION_CONTRACT_VERSION = 2


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


class SessionState:
    """In-memory view of a persisted v2 session blob."""

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
        if not candidate:
            return False
        stored_hash = self.data.get("session_secret_hash")
        if not stored_hash:
            return False
        return hmac.compare_digest(stored_hash, _secret_digest(candidate))

    def _require_contract(self) -> None:
        if self.data.get("document_contract_version") != SESSION_CONTRACT_VERSION:
            raise HTTPException(
                status_code=409,
                detail="This session uses an older document contract. Reload the worksheet to start a new session.",
            )

    def resolve_task_id(self, task_id: str = "", question_id: int | None = None) -> str:
        self._require_contract()
        tasks = self.data.get("tasks", {})
        if task_id:
            if task_id not in tasks:
                raise HTTPException(status_code=400, detail="Unknown task_id")
            return task_id
        if question_id is None:
            raise HTTPException(status_code=400, detail="task_id is required")
        resolved = self.data.get("legacy_question_ids", {}).get(str(question_id))
        if not resolved or resolved not in tasks:
            raise HTTPException(status_code=400, detail=f"Unknown question id: {question_id}")
        return resolved

    def default_response_region_id(self, task_id: str) -> str:
        task = self.get_task(task_id)
        default = task.get("default_response_region_id")
        if not default:
            raise HTTPException(status_code=409, detail="Task has no response destination")
        return default

    def get_task(self, task_id: str) -> dict[str, Any]:
        self._require_contract()
        task = self.data.get("tasks", {}).get(task_id)
        if task is None:
            raise HTTPException(status_code=400, detail="Unknown task_id")
        return task

    def get_response(self, task_id: str, response_region_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        response = task.get("responses", {}).get(response_region_id)
        if response is None:
            raise HTTPException(status_code=400, detail="Unknown response_region_id for task")
        return response

    # Compatibility accessors used by legacy test/support paths.  They resolve
    # an integer alias but never make the integer the authoritative identity.
    def get_question(self, question_id: int) -> dict | None:
        try:
            task_id = self.resolve_task_id(question_id=question_id)
            return self.get_response(task_id, self.default_response_region_id(task_id))
        except HTTPException:
            return None

    def set_confirmed(self, task_id: str, response_region_id: str, answer_text: str) -> None:
        response = self.get_response(task_id, response_region_id)
        response["draft_answer"] = answer_text
        response["confirmed_answer"] = answer_text
        response["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        response["write_tokens_used"] = response.get("write_tokens_used", [])

    def is_confirmed(self, task_id: str, response_region_id: str) -> bool:
        return bool(self.get_response(task_id, response_region_id).get("confirmed_answer", "").strip())

    def confirmed_answer(self, task_id: str, response_region_id: str) -> str:
        return self.get_response(task_id, response_region_id).get("confirmed_answer", "")

    def mark_written(self, task_id: str, response_region_id: str, answer_text: str) -> None:
        response = self.get_response(task_id, response_region_id)
        if response.get("confirmed_answer", "") != answer_text:
            raise HTTPException(status_code=403, detail="answer_text does not match confirmed answer")
        response["written_answer"] = answer_text
        response["written_at"] = datetime.now(timezone.utc).isoformat()


def _session_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=config.SESSION_TTL_HOURS)).isoformat()


def _task_snapshot(task: dict[str, Any]) -> str:
    """Fingerprint immutable task evidence independent of display-array position."""
    required_id = task.get("task_id")
    if not isinstance(required_id, str) or not required_id:
        raise ValueError("Session task requires a stable task_id")
    payload = {
        "task_id": required_id,
        "order": task.get("order"),
        "label": task.get("label"),
        "text": task.get("text", ""),
        "page_index": task.get("page_index"),
        "parent_task_id": task.get("parent_task_id"),
        "subpart": task.get("subpart"),
        "prompt_block_ids": task.get("prompt_block_ids", []),
        "choices": task.get("choices", []),
        "response_regions": task.get("response_regions", []),
        "response_target_id": task.get("response_target_id"),
        "response_type": task.get("response_type"),
        "side_panel_fallback": task.get("side_panel_fallback"),
        "review_status": task.get("review_status"),
        "approved": task.get("approved"),
    }
    return _hash_payload(payload)


def _response_snapshot(task_id: str, response: dict[str, Any]) -> str:
    response_id = response.get("id")
    if not isinstance(response_id, str) or not response_id:
        raise ValueError("Session response requires a stable response_region_id")
    return _hash_payload({"task_id": task_id, "response": response})


def _session_tasks(tasks: list[dict[str, Any]]) -> tuple[dict[str, dict], dict[str, str]]:
    session_tasks: dict[str, dict] = {}
    legacy_ids: dict[str, str] = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Session tasks must be objects")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("Session task requires a stable task_id")
        if task_id in session_tasks:
            raise ValueError(f"Duplicate session task_id: {task_id}")
        legacy_id = task.get("id")
        if isinstance(legacy_id, bool) or not isinstance(legacy_id, int):
            raise ValueError("Session task requires an integer legacy id")
        if str(legacy_id) in legacy_ids:
            raise ValueError(f"Duplicate legacy session question id: {legacy_id}")
        responses = list(task.get("response_regions") or [])
        default_response_id = task.get("response_target_id")
        response_state: dict[str, dict] = {}
        for response in responses:
            if not isinstance(response, dict):
                raise ValueError("Session response regions must be objects")
            response_id = response.get("id")
            if not isinstance(response_id, str) or not response_id:
                raise ValueError("Session response requires a stable response_region_id")
            if response_id in response_state:
                raise ValueError(f"Duplicate response_region_id: {response_id}")
            response_state[response_id] = {"response_snapshot": _response_snapshot(task_id, response)}
        if default_response_id not in response_state:
            # A zero-region task has a deterministic side-panel response target.
            if not isinstance(default_response_id, str) or not default_response_id:
                raise ValueError("Session task requires a response target")
            fallback = {
                "id": default_response_id,
                "task_id": task_id,
                "role": "answer",
                "safety": "side_panel",
                "safe_for_write": False,
            }
            response_state[default_response_id] = {"response_snapshot": _response_snapshot(task_id, fallback)}
        session_tasks[task_id] = {
            "task_snapshot": _task_snapshot(task),
            "legacy_question_id": legacy_id,
            "default_response_region_id": default_response_id,
            "responses": response_state,
        }
        legacy_ids[str(legacy_id)] = task_id
    return session_tasks, legacy_ids


def create_session(assignment_id: str, tasks: list[dict[str, Any]]) -> dict:
    session_id = str(uuid.uuid4())
    session_secret = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    session_tasks, legacy_ids = _session_tasks(tasks)
    blob = {
        "session_id": session_id,
        "assignment_id": assignment_id,
        "document_contract_version": SESSION_CONTRACT_VERSION,
        "session_secret_hash": _secret_digest(session_secret),
        "session_secret_version": 1,
        "created_at": now,
        "expires_at": _session_expires_at(),
        "tasks": session_tasks,
        "legacy_question_ids": legacy_ids,
        "metrics": {"errors_recovered": 0},
    }
    storage.upload_session_to_gcs(session_id, json.dumps(blob).encode("utf-8"))
    return {"session_id": session_id, "session_secret": session_secret, "expires_at": blob["expires_at"]}


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
    return config.get_session_hmac_secret().encode("utf-8")


def _secret_digest(session_secret: str) -> str:
    return hmac.new(_hmac_secret(), session_secret.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_write_token(payload: dict[str, str]) -> str:
    raw = _canonical_json(payload)
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(_hmac_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_write_token(write_token: str) -> dict[str, str]:
    try:
        encoded, signature = write_token.split(".", 1)
        expected = hmac.new(_hmac_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, UnicodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=403, detail="Invalid write_token") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=403, detail="Invalid write_token")
    required = {"sid", "task_id", "response_region_id", "fingerprint", "nonce"}
    if set(payload) != required or not all(isinstance(payload[key], str) for key in required):
        raise HTTPException(status_code=403, detail="Invalid write_token")
    return payload


def issue_write_token(state: SessionState, task_id: str, response_region_id: str, answer_text: str) -> str:
    if not answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text must be non-empty")
    if not state.is_confirmed(task_id, response_region_id):
        raise HTTPException(status_code=400, detail="Answer not confirmed for this response target")
    if state.confirmed_answer(task_id, response_region_id) != answer_text:
        raise HTTPException(status_code=400, detail="answer_text does not match confirmed answer")
    nonce = secrets.token_urlsafe(16)
    payload = {
        "sid": state.session_id,
        "task_id": task_id,
        "response_region_id": response_region_id,
        "fingerprint": _answer_fingerprint(answer_text),
        "nonce": nonce,
    }
    response = state.get_response(task_id, response_region_id)
    response.setdefault("pending_write_tokens", []).append(
        {"nonce": nonce, "issued_at": datetime.now(timezone.utc).isoformat()}
    )
    save_session(state)
    return _encode_write_token(payload)


def validate_write_token(
    state: SessionState,
    task_id: str,
    response_region_id: str,
    answer_candidate: str,
    write_token: str,
) -> None:
    if not write_token:
        raise HTTPException(status_code=403, detail="write_token is required")
    if not answer_candidate.strip():
        raise HTTPException(status_code=400, detail="answer_candidate must be non-empty")
    payload = _decode_write_token(write_token)
    if (
        payload["sid"] != state.session_id
        or payload["task_id"] != task_id
        or payload["response_region_id"] != response_region_id
        or payload["fingerprint"] != _answer_fingerprint(answer_candidate)
    ):
        raise HTTPException(status_code=403, detail="write_token does not match confirmed response")
    response = state.get_response(task_id, response_region_id)
    pending = response.get("pending_write_tokens", [])
    if not any(item.get("nonce") == payload["nonce"] for item in pending):
        raise HTTPException(status_code=403, detail="write_token already used or unknown")
    response["pending_write_tokens"] = [
        item for item in pending if item.get("nonce") != payload["nonce"]
    ]
    response.setdefault("write_tokens_used", []).append(payload["nonce"])
    save_session(state)


def validate_task_snapshot(
    state: SessionState,
    task_id: str,
    response_region_id: str,
    current_task: dict[str, Any],
) -> None:
    task_state = state.get_task(task_id)
    expected = task_state.get("task_snapshot", "")
    if not expected or not hmac.compare_digest(expected, _task_snapshot(current_task)):
        raise HTTPException(status_code=409, detail="Task changed since confirmation. Reload and confirm again.")
    target = next(
        (
            item
            for item in current_task.get("response_regions", [])
            if item.get("id") == response_region_id
        ),
        None,
    )
    if target is None and current_task.get("response_target_id") == response_region_id:
        target = {
            "id": response_region_id,
            "task_id": task_id,
            "role": "answer",
            "safety": "side_panel",
            "safe_for_write": False,
        }
    if target is None:
        raise HTTPException(status_code=409, detail="Response target changed. Reload and confirm again.")
    expected_target = state.get_response(task_id, response_region_id).get("response_snapshot", "")
    if not expected_target or not hmac.compare_digest(
        expected_target, _response_snapshot(task_id, target)
    ):
        raise HTTPException(status_code=409, detail="Response target changed. Reload and confirm again.")


def mark_answer_written(
    state: SessionState,
    task_id: str,
    response_region_id: str,
    answer_text: str,
    current_task: dict[str, Any],
) -> None:
    validate_task_snapshot(state, task_id, response_region_id, current_task)
    state.mark_written(task_id, response_region_id, answer_text)
    save_session(state)


def written_answers_for_export(
    session_id: str,
    session_secret: str,
    assignment_id: str,
    current_tasks: list[dict[str, Any]],
) -> list[dict]:
    state = load_session(session_id)
    if state.assignment_id != assignment_id:
        raise HTTPException(status_code=403, detail="Session does not match assignment")
    if not state.verify_session_secret(session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    state._require_contract()
    current_by_id = {str(task.get("task_id")): task for task in current_tasks}
    answers = []
    for task_id, task_state in state.data.get("tasks", {}).items():
        current_task = current_by_id.get(task_id)
        for response_region_id, response_state in task_state.get("responses", {}).items():
            if not str(response_state.get("written_answer", "")).strip():
                continue
            if current_task is None:
                raise HTTPException(status_code=409, detail="Task changed since writing. Reload before export.")
            validate_task_snapshot(state, task_id, response_region_id, current_task)
            answers.append(
                {
                    "task_id": task_id,
                    "response_region_id": response_region_id,
                    "answer_text": response_state["written_answer"],
                }
            )
    return answers


def confirm_answer(
    session_id: str,
    session_secret: str,
    *,
    task_id: str = "",
    response_region_id: str = "",
    question_id: int | None = None,
    answer_text: str,
) -> dict:
    if not answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text must be non-empty")
    state = load_session(session_id)
    if not state.verify_session_secret(session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    resolved_task_id = state.resolve_task_id(task_id, question_id)
    resolved_response_id = response_region_id or state.default_response_region_id(resolved_task_id)
    state.get_response(resolved_task_id, resolved_response_id)
    state.set_confirmed(resolved_task_id, resolved_response_id, answer_text)
    save_session(state)
    write_token = issue_write_token(state, resolved_task_id, resolved_response_id, answer_text)
    return {
        "task_id": resolved_task_id,
        "response_region_id": resolved_response_id,
        "confirmed": True,
        "write_token": write_token,
    }


def restore_session_for_client(session_id: str, session_secret: str) -> dict:
    state = load_session(session_id)
    if not state.verify_session_secret(session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    state._require_contract()
    responses: dict[str, dict] = {}
    for task_id, task in state.data.get("tasks", {}).items():
        for response_id, response in task.get("responses", {}).items():
            responses[response_id] = {
                "task_id": task_id,
                "confirmed_answer": response.get("confirmed_answer", ""),
                "written_answer": response.get("written_answer", ""),
                "confirmed": bool(response.get("confirmed_answer", "").strip()),
                "written": bool(response.get("written_answer", "").strip()),
            }
    return {
        "session_id": session_id,
        "assignment_id": state.assignment_id,
        "expires_at": state.data.get("expires_at"),
        "responses": responses,
    }


def init_question_ids_from_manifest(manifest: AssignmentManifest) -> list[int]:
    """Compatibility-only display aliases; canonical state uses task IDs."""
    return [task.legacy_question_id for task in manifest.document.tasks]
