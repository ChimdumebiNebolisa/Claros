"""Integration tests for main FastAPI app (static/export routes only; no GCS/Gemini)."""
import pytest
import fitz

from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
from manifest import build_manifest
from rate_limit import SlidingWindowRateLimiter
from tests.conftest import TEST_ASSIGNMENT_ID


@pytest.fixture(autouse=True)
def bypass_assignment_capability(monkeypatch):
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)

client = TestClient(main_module.app)


def _fake_manifest(_assignment_id: str = TEST_ASSIGNMENT_ID):
    return build_manifest(
        _assignment_id,
        "Mock Assignment",
        questions=[
            {"id": 1, "task_id": "task-first", "text": "First question?"},
            {"id": 2, "task_id": "task-second", "text": "Second question?"},
        ],
    )


def _fake_pdf_bytes():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Mock Assignment")
    content = document.tobytes()
    document.close()
    return content


def _mock_export_source(monkeypatch):
    manifest = _fake_manifest()
    monkeypatch.setattr(
        main_module,
        "load_canonical_export_source",
        lambda _id: (manifest, _fake_pdf_bytes()),
    )
    return manifest


def test_index_returns_html():
    """GET / returns HTML (Claros landing page or fallback)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"<" in response.content and b"html" in response.content.lower()


def test_health_is_dependency_free():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_session_start_maps_expired_assignment(monkeypatch):
    def raise_expired(_assignment_id):
        raise assignment_service.AssignmentExpiredError("expired")

    monkeypatch.setattr(assignment_service, "load_assignment_manifest", raise_expired)
    response = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})
    assert response.status_code == 410
    assert response.json()["detail"] == "Assignment expired"


def test_session_start_rejects_a_changed_source_before_allocating_state(monkeypatch):
    created = []

    def raise_source_mismatch(_assignment_id):
        raise assignment_service.AssignmentSourceMismatchError("changed")

    monkeypatch.setattr(
        assignment_service,
        "load_assignment_manifest_for_client",
        raise_source_mismatch,
    )
    monkeypatch.setattr(
        session_service,
        "create_session",
        lambda *_args: created.append(_args),
    )

    response = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})

    assert response.status_code == 409
    assert created == []


def test_session_start_is_rate_limited_before_allocating_another_durable_session(monkeypatch):
    monkeypatch.setattr(main_module, "rate_limiter", SlidingWindowRateLimiter())
    monkeypatch.setattr(main_module.config, "MAX_SESSION_STARTS_PER_MINUTE", 1)
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", _fake_manifest)
    created = []

    def create_session(assignment_id, questions):
        created.append((assignment_id, questions))
        return {"session_id": "only-session", "session_secret": "secret", "expires_at": "later"}

    monkeypatch.setattr(session_service, "create_session", create_session)
    first = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})
    second = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})

    assert first.status_code == 200
    assert second.status_code == 429
    assert "content-security-policy" in second.headers
    assert len(created) == 1


def test_landing_has_no_app_workspace():
    """GET / serves marketing landing without functional upload workspace."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"id=\"uploadZone\"" not in response.content
    assert b"id=\"micBtn\"" not in response.content
    assert b"Keep the page in view" in response.content


def test_app_sample_query_param_hint():
    """GET /app loads external app.js with sample=1 auto-load deep link."""
    response = client.get("/app")
    assert response.status_code == 200
    assert b"/app.js" in response.content


def test_app_js_served():
    """Worksheet client script is served as a static asset."""
    response = client.get("/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    assert b"loadSamplePdf" in response.content
    assert b"/api/samples" in response.content
    assert b"sample" in response.content
    assert b"showVoiceFallback" in response.content
    assert b"ClarosWorksheetView" in response.content
    assert b"ClarosUiState" in response.content


def test_app_returns_html():
    """GET /app returns the functional worksheet app."""
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"id=\"uploadBtn\"" in response.content


def test_styles_css_served():
    """Frontend CSS assets for landing and app pages."""
    for name in ("tokens.css", "landing.css", "app.css"):
        response = client.get(f"/styles/{name}")
        assert response.status_code == 200
        assert "css" in response.headers.get("content-type", "").lower()


def test_test_page_returns_html():
    """GET /test is not a public production surface."""
    response = client.get("/test")
    assert response.status_code == 404


def test_genai_bundle_served_and_non_empty():
    """Bundled Gemini SDK must be present (Cloud Run / CI smoke)."""
    response = client.get("/genai.bundle.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    assert len(response.content) > 1000


def test_test_assignment_pdf_served():
    """Default sample alias serves the official short-answer PDF."""
    response = client.get("/sample-assignment.pdf")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.content[:4] == b"%PDF"
    from sample_catalog import get_product_sample

    assert response.content == get_product_sample(None).pdf_path.read_bytes()


def test_session_rules_js_served():
    """Session gating script for the worksheet UI."""
    response = client.get("/session-rules.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    assert b"ClarosSessionRules" in response.content


def test_question_view_js_served():
    response = client.get("/question-view.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    assert b"ClarosQuestionView" in response.content


@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/ui-state.js", b"ClarosUiState"),
        ("/worksheet-view.js", b"ClarosWorksheetView"),
    ],
)
def test_workspace_modules_served(path, marker):
    response = client.get(path)
    assert response.status_code == 200
    assert marker in response.content


def test_sample_page_preview_served():
    response = client.get("/sample-page.png")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")


def test_sample_workspace_preview_served():
    response = client.get("/sample-workspace.png")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")


def test_assignment_page_preview_served(monkeypatch):
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", _fake_manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: _fake_pdf_bytes())

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/1.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")


def test_assignment_page_preview_rejects_missing_page(monkeypatch):
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", _fake_manifest)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: _fake_pdf_bytes())

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/99.png")

    assert response.status_code == 404


def test_assignment_page_preview_rejects_a_changed_source(monkeypatch):
    def raise_source_mismatch(*_args):
        raise assignment_service.AssignmentSourceMismatchError("changed")

    monkeypatch.setattr(main_module, "render_assignment_page", raise_source_mismatch)

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/1.png")

    assert response.status_code == 409


def test_export_post_returns_pdf_attachment(monkeypatch):
    """POST /export renders only answers supplied by the server-side session."""
    manifest = _mock_export_source(monkeypatch)
    task = manifest.to_questions_dict()[0]
    monkeypatch.setattr(
        session_service,
        "written_answers_for_export",
        lambda *_args: [
            {
                "task_id": task["task_id"],
                "response_region_id": task["response_target_id"],
                "answer_text": "First answer",
            }
        ],
    )

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session-1", "session_secret": "session-secret"},
    )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.headers.get("content-disposition") == f'attachment; filename="claros-{TEST_ASSIGNMENT_ID}.pdf"'
    assert response.content.startswith(b"%PDF")


def test_export_uses_the_exact_manifest_snapshot_that_was_validated(monkeypatch):
    original_manifest = build_manifest(
        TEST_ASSIGNMENT_ID,
        "Mock Assignment",
        questions=[{"id": 1, "task_id": "task-original", "text": "Original task evidence"}],
    )
    changed_manifest = build_manifest(
        TEST_ASSIGNMENT_ID,
        "Mock Assignment",
        questions=[{"id": 1, "task_id": "task-original", "text": "Changed task evidence"}],
    )
    calls = []

    def load_export_source(_assignment_id):
        calls.append(_assignment_id)
        return (original_manifest if len(calls) == 1 else changed_manifest), _fake_pdf_bytes()

    monkeypatch.setattr(main_module, "load_canonical_export_source", load_export_source)
    original_task = original_manifest.to_questions_dict()[0]
    monkeypatch.setattr(
        session_service,
        "written_answers_for_export",
        lambda _sid, _secret, _aid, questions: (
            [
                {
                    "task_id": original_task["task_id"],
                    "response_region_id": original_task["response_target_id"],
                    "answer_text": "Confirmed answer",
                }
            ]
            if questions == original_manifest.to_questions_dict()
            else pytest.fail("export validated a changed task snapshot")
        ),
    )

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session-1", "session_secret": "session-secret"},
    )

    assert response.status_code == 200
    assert calls == [TEST_ASSIGNMENT_ID]
    document = fitz.open(stream=response.content, filetype="pdf")
    try:
        exported_text = " ".join(page.get_text() for page in document)
    finally:
        document.close()
    assert "Original task evidence" in exported_text
    assert "Changed task evidence" not in exported_text


def test_export_post_accepts_long_answer_body(monkeypatch):
    """Long confirmed answers are loaded from server-side session state."""
    manifest = _mock_export_source(monkeypatch)
    task = manifest.to_questions_dict()[0]
    long_answer = "This sentence makes the answer long enough to avoid query-string export. " * 40
    monkeypatch.setattr(
        session_service,
        "written_answers_for_export",
        lambda *_args: [
            {
                "task_id": task["task_id"],
                "response_region_id": task["response_target_id"],
                "answer_text": long_answer,
            }
        ],
    )

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session-1", "session_secret": "session-secret"},
    )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_export_post_rejects_client_supplied_answers(monkeypatch):
    """Client answer text cannot bypass confirmation via the export request."""
    _mock_export_source(monkeypatch)

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session-1", "session_secret": "session-secret", "answers": [{}]},
    )

    assert response.status_code == 422


def test_export_get_is_disabled(monkeypatch):
    """Legacy query-string export is disabled to prevent answer injection."""
    _mock_export_source(monkeypatch)

    response = client.get(
        f"/export/{TEST_ASSIGNMENT_ID}",
        params={"answers": "[{}]"},
    )

    assert response.status_code == 405


def test_export_get_is_disabled_for_non_list_payloads(monkeypatch):
    """No query-string payload is accepted by the export route."""
    _mock_export_source(monkeypatch)

    response = client.get(
        f"/export/{TEST_ASSIGNMENT_ID}",
        params={"answers": "{}"},
    )

    assert response.status_code == 405
