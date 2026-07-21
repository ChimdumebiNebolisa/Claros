"""API error semantics: distinguish missing assignments from backend failures."""
from fastapi.testclient import TestClient

import main as main_module
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


def test_write_rejects_missing_assignment_capability_before_lookup():
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={"question_id": 1, "conversation": [], "answer_candidate": ""},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Assignment capability is required"


def test_write_does_not_disclose_backend_state_without_capability():
    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={"question_id": 1, "conversation": [], "answer_candidate": ""},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Assignment capability is required"


def test_export_rejects_arbitrary_client_answers():
    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"answers": [{"question_id": 1, "answer_text": "Answer"}]},
    )
    assert response.status_code == 422


def test_export_requires_server_session_evidence():
    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={},
    )
    assert response.status_code == 422


def test_invalid_assignment_id_returns_422():
    response = client.post(
        "/api/write/not-a-uuid",
        json={"question_id": 1, "conversation": [], "answer_candidate": ""},
    )
    assert response.status_code == 422
