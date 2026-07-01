"""Integration tests for main FastAPI app (static/export routes only; no GCS/Gemini)."""
import pytest

from fastapi.testclient import TestClient

import main as main_module

client = TestClient(main_module.app)


def _fake_load_assignment(_assignment_id: str):
    return "Mock Assignment", [
        {"id": 1, "text": "First question?"},
        {"id": 2, "text": "Second question?"},
    ]


def test_index_returns_html():
    """GET / returns HTML (Claros landing page or fallback)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"<" in response.content and b"html" in response.content.lower()


def test_landing_has_no_app_workspace():
    """GET / serves marketing landing without functional upload workspace."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"id=\"uploadZone\"" not in response.content
    assert b"id=\"micBtn\"" not in response.content
    assert b"Built for students" in response.content


def test_app_sample_query_param_hint():
    """GET /app includes sample=1 auto-load for landing Try sample deep link."""
    response = client.get("/app")
    assert response.status_code == 200
    assert b"sample" in response.content
    assert b"loadSamplePdf" in response.content


def test_app_returns_html():
    """GET /app returns the functional worksheet app."""
    response = client.get("/app")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"id=\"micBtn\"" in response.content or b"id=\"uploadZone\"" in response.content


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


def test_export_post_returns_pdf_attachment(monkeypatch):
    """POST /export accepts answer JSON and returns a downloadable PDF."""
    monkeypatch.setattr(main_module, "load_assignment_from_gcs", _fake_load_assignment)

    response = client.post(
        "/export/mock-assignment-id",
        json={"answers": [{"question_id": 1, "answer_text": "First answer"}]},
    )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.headers.get("content-disposition") == 'attachment; filename="claros-mock-assignment-id.pdf"'
    assert response.content.startswith(b"%PDF")


def test_export_post_accepts_long_answer_body(monkeypatch):
    """Long answers travel in the POST body instead of the URL query string."""
    monkeypatch.setattr(main_module, "load_assignment_from_gcs", _fake_load_assignment)
    long_answer = "This sentence makes the answer long enough to avoid query-string export. " * 200

    response = client.post(
        "/export/mock-assignment-id",
        json={"answers": [{"question_id": 1, "answer_text": long_answer}]},
    )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").lower().startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
