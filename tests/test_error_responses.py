"""API error semantics: distinguish missing assignments from backend failures."""
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


def test_write_returns_404_when_assignment_missing(monkeypatch):
    def raise_not_found(_assignment_id: str):
        raise ValueError("No PDF found")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_not_found)

    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={"question_id": 1, "conversation": [], "answer_candidate": ""},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Assignment not found"


def test_write_returns_500_when_backend_fails(monkeypatch):
    def raise_backend(_assignment_id: str):
        raise RuntimeError("GCS unavailable")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_backend)

    response = client.post(
        f"/api/write/{TEST_ASSIGNMENT_ID}",
        json={"question_id": 1, "conversation": [], "answer_candidate": ""},
    )
    assert response.status_code == 500
    assert "Could not load assignment" in response.json()["detail"]


def test_export_returns_404_when_assignment_missing(monkeypatch):
    def raise_not_found(_assignment_id: str):
        raise ValueError("No PDF found")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_not_found)

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"answers": [{"question_id": 1, "answer_text": "Answer"}]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Assignment not found"


def test_export_returns_500_when_backend_fails(monkeypatch):
    def raise_backend(_assignment_id: str):
        raise RuntimeError("GCS unavailable")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_backend)

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"answers": [{"question_id": 1, "answer_text": "Answer"}]},
    )
    assert response.status_code == 500
    assert "Could not load assignment for export" in response.json()["detail"]


def test_invalid_assignment_id_returns_422():
    response = client.post(
        "/api/write/not-a-uuid",
        json={"question_id": 1, "conversation": [], "answer_candidate": ""},
    )
    assert response.status_code == 422
