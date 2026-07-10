"""API tests for parse diagnostics and assignment deletion."""
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


def test_parse_diagnostics_returns_manifest_summary(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_parse_diagnostics",
        lambda _id: {
            "assignment_id": TEST_ASSIGNMENT_ID,
            "parse_status": "ok",
            "parse_warnings": [],
            "num_questions": 2,
            "question_ids": [1, 2],
            "expires_at": None,
        },
    )
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/parse-diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "ok"
    assert body["num_questions"] == 2


def test_delete_assignment_route(monkeypatch):
    called = {}

    def fake_delete(assignment_id):
        called["id"] = assignment_id

    monkeypatch.setattr(main_module, "delete_assignment", fake_delete)
    response = client.delete(f"/api/assignments/{TEST_ASSIGNMENT_ID}")
    assert response.status_code == 200
    assert called["id"] == TEST_ASSIGNMENT_ID
