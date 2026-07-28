"""API tests for parse diagnostics and assignment deletion."""
import pytest
from fastapi.testclient import TestClient

import assignment_service
import main as main_module
from manifest import build_manifest
from tests.conftest import TEST_ASSIGNMENT_ID

client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def bypass_assignment_capability(monkeypatch):
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)


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


def test_page_preview_is_rate_limited_after_authorization(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main_module,
        "_enforce_rate_limit",
        lambda _request, bucket, limit, _capability=None: calls.append((bucket, limit)),
    )
    monkeypatch.setattr(main_module, "render_assignment_page", lambda *_args: b"png")
    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/1.png")
    assert response.status_code == 200
    assert calls == [("page_render", main_module.config.MAX_PAGE_RENDERS_PER_MINUTE)]


def _teacher_manifest():
    return build_manifest(
        assignment_id=TEST_ASSIGNMENT_ID,
        title="Teacher packet",
        questions=[
            {
                "id": 1,
                "task_id": "q1-test",
                "text": "Explain the result.",
                "page": 1,
                "page_index": 0,
                "page_role": "student_worksheet",
                "answer_region_status": "side_panel",
                "source_blocks": ["page-0-native-1"],
                "needs_layout_review": True,
            }
        ],
        review_mode="teacher",
        review_status="draft",
    )


def test_teacher_review_get_returns_uncertain_tasks(monkeypatch):
    monkeypatch.setattr(
        assignment_service,
        "load_assignment_manifest",
        lambda _assignment_id: _teacher_manifest(),
    )
    response = client.get(f"/api/teacher/assignments/{TEST_ASSIGNMENT_ID}")
    assert response.status_code == 200
    assert response.json()["document"]["tasks"][0]["id"] == "q1-test"


def test_teacher_review_post_validates_and_forwards_actions(monkeypatch):
    captured = {}

    def fake_review(assignment_id, actions, *, finalize):
        captured.update(assignment_id=assignment_id, actions=actions, finalize=finalize)
        return _teacher_manifest()

    monkeypatch.setattr(main_module, "review_assignment", fake_review)
    response = client.post(
        f"/api/teacher/assignments/{TEST_ASSIGNMENT_ID}/review",
        json={
            "actions": [{"action": "accept", "task_id": "q1-test", "approve": True}],
            "finalize": False,
        },
    )
    assert response.status_code == 200
    assert captured == {
        "assignment_id": TEST_ASSIGNMENT_ID,
        "actions": [
            {"action": "accept", "task_id": "q1-test", "approve": True}
        ],
        "finalize": False,
    }
