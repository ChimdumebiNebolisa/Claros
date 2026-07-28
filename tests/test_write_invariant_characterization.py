"""Characterization tests for write contract and parser fallback behavior."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
from tests.conftest import TEST_ASSIGNMENT_ID


@pytest.fixture
def write_client(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: (
            "Mock",
            [{"id": 1, "text": "Q?", "answer_region": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.1}}],
        ),
    )
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)
    return TestClient(main_module.app)


def test_write_rejects_empty_candidate(write_client):
    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [],
            "answer_candidate": "",
        },
    )
    assert response.status_code == 400
    assert "non-empty" in response.json()["detail"]


def test_write_rejects_missing_write_token(write_client):
    response = write_client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={
            "question_id": 1,
            "conversation": [{"speaker": "user", "text": "My answer is 5"}],
            "answer_candidate": "5",
        },
    )
    assert response.status_code == 403


def test_parser_unsupported_layout_has_no_fallback_question(tmp_pdf_no_questions):
    from parser import parse_pdf_with_diagnostics

    _title, questions, warnings, status = parse_pdf_with_diagnostics(tmp_pdf_no_questions)
    assert questions == []
    assert status == "unsupported_layout"
    assert "unsupported_layout" in warnings


def test_session_confirm_issues_write_token(monkeypatch, write_client):
    task_id = "task-q1"
    response_region_id = "task-q1:side-panel"
    created = {
        "blob": {
            "session_id": "550e8400-e29b-41d4-a716-446655440001",
            "assignment_id": TEST_ASSIGNMENT_ID,
            "document_contract_version": session_service.SESSION_CONTRACT_VERSION,
            "session_secret_hash": session_service._secret_digest("secret-abc"),
            "expires_at": "2099-01-01T00:00:00+00:00",
            "tasks": {
                task_id: {
                    "legacy_question_id": 1,
                    "default_response_region_id": response_region_id,
                    "responses": {response_region_id: {"response_snapshot": "fixture-response"}},
                }
            },
            "legacy_question_ids": {"1": task_id},
        }
    }

    def fake_load(session_id):
        from session_service import SessionState

        return SessionState(created["blob"])

    def fake_save(state):
        created["blob"] = state.data

    monkeypatch.setattr(session_service, "load_session", fake_load)
    monkeypatch.setattr(session_service, "save_session", fake_save)

    confirm = write_client.post(
        "/api/session/550e8400-e29b-41d4-a716-446655440001/confirm",
        json={
            "session_secret": "secret-abc",
            "task_id": task_id,
            "response_region_id": response_region_id,
            "answer_text": "My final answer is 7",
        },
    )
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["task_id"] == task_id
    assert body["response_region_id"] == response_region_id
    assert body["confirmed"] is True
    assert body["write_token"]
