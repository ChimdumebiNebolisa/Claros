"""Integration tests for main FastAPI app (static/export routes only; no GCS/Gemini)."""
import pytest
import fitz

from fastapi.testclient import TestClient

import assignment_service
import main as main_module
import session_service
from tests.conftest import TEST_ASSIGNMENT_ID


@pytest.fixture(autouse=True)
def bypass_assignment_capability(monkeypatch):
    monkeypatch.setattr(main_module, "_require_assignment_capability", lambda *_args: None)

client = TestClient(main_module.app)


def _fake_load_assignment(_assignment_id: str):
    return "Mock Assignment", [
        {"id": 1, "text": "First question?"},
        {"id": 2, "text": "Second question?"},
    ]


def _fake_pdf_bytes():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Mock Assignment")
    content = document.tobytes()
    document.close()
    return content


def _mock_export_source(monkeypatch):
    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", _fake_load_assignment)
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: _fake_pdf_bytes())


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

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_expired)
    response = client.post("/api/session/start", json={"assignment_id": TEST_ASSIGNMENT_ID})
    assert response.status_code == 410
    assert response.json()["detail"] == "Assignment expired"


def test_landing_has_no_app_workspace():
    """GET / serves marketing landing without functional upload workspace."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"id=\"uploadZone\"" not in response.content
    assert b"id=\"micBtn\"" not in response.content
    assert b"Built for students" in response.content


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
    """GET /test returns HTML (voice test page or 404 if file missing)."""
    response = client.get("/test")
    # 200 if test_voice.html exists, 404 otherwise
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert "text/html" in response.headers.get("content-type", "")


def test_genai_bundle_served_and_non_empty():
    """Bundled Gemini SDK must be present (Cloud Run / CI smoke)."""
    response = client.get("/genai.bundle.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "").lower()
    assert len(response.content) > 1000


def test_test_assignment_pdf_served():
    """Built-in test PDF is shipped for local/demo use."""
    response = client.get("/test-assignment.pdf")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.content[:4] == b"%PDF"


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


def test_assignment_page_preview_served(monkeypatch):
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: object())
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: _fake_pdf_bytes())

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/1.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")


def test_assignment_page_preview_rejects_missing_page(monkeypatch):
    monkeypatch.setattr(assignment_service, "load_assignment_manifest", lambda _id: object())
    monkeypatch.setattr(assignment_service, "_download_pdf_bytes", lambda _id: _fake_pdf_bytes())

    response = client.get(f"/api/assignments/{TEST_ASSIGNMENT_ID}/pages/99.png")

    assert response.status_code == 404


def test_export_post_returns_pdf_attachment(monkeypatch):
    """POST /export renders only answers supplied by the server-side session."""
    _mock_export_source(monkeypatch)
    monkeypatch.setattr(
        session_service,
        "written_answers_for_export",
        lambda *_args: [{"question_id": 1, "answer_text": "First answer"}],
    )

    response = client.post(
        f"/export/{TEST_ASSIGNMENT_ID}",
        json={"session_id": "session-1", "session_secret": "session-secret"},
    )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.headers.get("content-disposition") == f'attachment; filename="claros-{TEST_ASSIGNMENT_ID}.pdf"'
    assert response.content.startswith(b"%PDF")


def test_export_post_accepts_long_answer_body(monkeypatch):
    """Long confirmed answers are loaded from server-side session state."""
    _mock_export_source(monkeypatch)
    long_answer = "This sentence makes the answer long enough to avoid query-string export. " * 40
    monkeypatch.setattr(
        session_service,
        "written_answers_for_export",
        lambda *_args: [{"question_id": 1, "answer_text": long_answer}],
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
