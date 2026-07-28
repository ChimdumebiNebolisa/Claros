"""Assignment owner-capability regression coverage."""
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
from manifest import build_manifest
from tests.conftest import TEST_ASSIGNMENT_ID

_TASK_ID = "task-capability"
_RESPONSE_REGION_ID = f"{_TASK_ID}:side-panel"


def _manifest(capability: str):
    return build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title="Capability test",
        questions=[{"id": 1, "task_id": _TASK_ID, "text": "Question"}],
        assignment_capability_hash=assignment_service.assignment_capability_digest(capability),
    )


def test_sensitive_routes_reject_missing_or_wrong_assignment_capability(monkeypatch):
    capability = "owner-capability"
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: _manifest(capability))
    client = TestClient(main_module.app)

    missing = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})
    wrong = client.post(
        "/api/session/start",
        headers={"X-Assignment-Capability": "wrong"},
        json={"assignment_id": TEST_ASSIGNMENT_ID},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403


def test_capability_authorizes_session_but_export_uses_only_written_server_answers(monkeypatch):
    capability = "owner-capability"
    stored = {}
    manifest = _manifest(capability)
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: manifest)
    monkeypatch.setattr(
        main_module,
        "load_canonical_export_source",
        lambda _id: (manifest, b"mock-pdf"),
    )
    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", lambda sid, payload, **_kwargs: stored.setdefault(sid, payload))
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", lambda sid, **_kwargs: stored[sid])
    monkeypatch.setattr(
        session_service,
        "written_answers_for_export",
        lambda *_args: [
            {
                "task_id": _TASK_ID,
                "response_region_id": _RESPONSE_REGION_ID,
                "answer_text": "written",
            }
        ],
    )
    monkeypatch.setattr(main_module, "build_export_response", lambda _id, answers, **_kwargs: {"answers": answers})
    client = TestClient(main_module.app)
    headers = {"X-Assignment-Capability": capability}

    started = client.post("/api/session/start", headers=headers, json={"assignment_id": TEST_ASSIGNMENT_ID})
    assert started.status_code == 200

    bypass = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session", "session_secret": "session-secret"},
    )
    injected = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        headers=headers,
        json={
            "session_id": "session",
            "session_secret": "session-secret",
            "answers": [
                {
                    "task_id": _TASK_ID,
                    "response_region_id": _RESPONSE_REGION_ID,
                    "answer_text": "injected",
                }
            ],
        },
    )
    authorized = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        headers=headers,
        json={"session_id": "session", "session_secret": "session-secret"},
    )

    assert bypass.status_code == 403
    assert injected.status_code == 422
    assert authorized.status_code == 200
    assert authorized.json() == {
        "answers": [
            {
                "task_id": _TASK_ID,
                "response_region_id": _RESPONSE_REGION_ID,
                "answer_text": "written",
            }
        ]
    }


def test_written_answer_is_persisted_in_session_state(monkeypatch):
    stored = {}

    def upload(session_id, payload, **_kwargs):
        stored[session_id] = payload

    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", upload)
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", lambda sid, **_kwargs: stored[sid])

    question = _manifest("session-capability").to_questions_dict()[0]
    created = session_service.create_session(TEST_ASSIGNMENT_ID, [question])
    state = session_service.load_session(created["session_id"])
    state.set_confirmed(_TASK_ID, _RESPONSE_REGION_ID, "Student answer")
    session_service.save_session(state)
    session_service.mark_answer_written(
        state,
        _TASK_ID,
        _RESPONSE_REGION_ID,
        "Student answer",
        question,
    )

    restored = json.loads(stored[created["session_id"]])
    assert (
        restored["tasks"][_TASK_ID]["responses"][_RESPONSE_REGION_ID]["written_answer"]
        == "Student answer"
    )


def test_export_rejects_a_task_that_changed_since_the_confirmed_write(monkeypatch):
    stored = {}

    def upload(session_id, payload, **_kwargs):
        stored[session_id] = payload

    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", upload)
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", lambda sid, **_kwargs: stored[sid])

    question = build_manifest(
        TEST_ASSIGNMENT_ID,
        "Capability test",
        questions=[
            {
                "id": 1,
                "task_id": "task-source",
                "text": "State the conclusion.",
            }
        ],
    ).to_questions_dict()[0]
    task_id = question["task_id"]
    response_region_id = question["response_target_id"]
    created = session_service.create_session(TEST_ASSIGNMENT_ID, [question])
    state = session_service.load_session(created["session_id"])
    state.set_confirmed(task_id, response_region_id, "Exact confirmed answer")
    session_service.save_session(state)
    session_service.mark_answer_written(
        state,
        task_id,
        response_region_id,
        "Exact confirmed answer",
        question,
    )

    exported = session_service.written_answers_for_export(
        created["session_id"],
        created["session_secret"],
        TEST_ASSIGNMENT_ID,
        [question],
    )
    assert exported == [
        {
            "task_id": task_id,
            "response_region_id": response_region_id,
            "answer_text": "Exact confirmed answer",
        }
    ]

    changed_question = {**question, "text": "A teacher changed this task after confirmation."}
    with pytest.raises(HTTPException) as exc:
        session_service.written_answers_for_export(
            created["session_id"],
            created["session_secret"],
            TEST_ASSIGNMENT_ID,
            [changed_question],
        )
    assert exc.value.status_code == 409
