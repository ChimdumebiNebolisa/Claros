"""Session config endpoint tests with mocked Gemini/GCS dependencies."""
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


def test_session_config_invalid_assignment_id_returns_422():
    response = client.get("/api/session-config/not-a-uuid")
    assert response.status_code == 422


def test_session_config_missing_assignment_returns_404(monkeypatch):
    def raise_missing(_assignment_id: str):
        raise ValueError("No PDF found")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_missing)

    response = client.get(f"/api/session-config/{TEST_ASSIGNMENT_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Assignment not found"


def test_session_config_token_failure_returns_500(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_from_gcs",
        lambda _id: ("Title", [{"id": 1, "text": "Q?"}]),
    )

    def raise_token(_assignment_id: str):
        raise RuntimeError("Ephemeral token creation failed")

    monkeypatch.setattr(main_module, "create_session_config", raise_token)

    response = client.get(f"/api/session-config/{TEST_ASSIGNMENT_ID}")
    assert response.status_code == 500
    assert "Session setup failed" in response.json()["detail"]


def test_session_config_success_returns_payload(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "create_session_config",
        lambda _id: {
            "token": "tok",
            "model": "gemini-live",
            "system_prompt": "prompt",
            "title": "Title",
            "questions": [{"id": 1, "text": "Q?"}],
        },
    )

    response = client.get(f"/api/session-config/{TEST_ASSIGNMENT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["token"] == "tok"
    assert body["questions"][0]["id"] == 1
