"""Additional static route and asset coverage."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main as main_module

client = TestClient(main_module.app)
ROOT = Path(__file__).resolve().parent.parent


def test_styles_rejects_path_traversal():
    response = client.get("/styles/../main.py")
    assert response.status_code == 404


def test_styles_rejects_non_css_extension():
    response = client.get("/styles/app.js")
    assert response.status_code == 404


def test_favicon_and_logo_served():
    for path in ("/favicon.png", "/logo.png"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("image/")


def test_landing_page_links_to_app():
    response = client.get("/")
    assert response.status_code == 200
    assert b'href="/app"' in response.content


def test_active_frontend_routes_serve_the_documented_entrypoints():
    for route, filename in (("/", "landing.html"), ("/app", "app.html")):
        response = client.get(route)
        expected = (ROOT / "frontend" / filename).read_bytes()
        assert response.status_code == 200
        assert response.content == expected


def test_legacy_frontend_documents_are_not_routed():
    for route in ("/index.html", "/index.backup.html"):
        response = client.get(route)
        assert response.status_code == 404


def test_debug_gemini_disabled_by_default():
    response = client.get("/debug-gemini")
    assert response.status_code == 404


def test_legacy_debug_routes_are_disabled_by_default():
    for path in ("/test", "/test-assignment.pdf"):
        response = client.get(path)
        assert response.status_code == 404


@pytest.mark.parametrize("path", ("/", "/app", "/app.js", "/styles/app.css", "/does-not-exist"))
def test_security_headers_cover_html_assets_and_not_found_responses(path):
    response = client.get(path)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), geolocation=(), payment=(), usb=(), microphone=(self)"

    directives = {item.strip() for item in response.headers["content-security-policy"].split(";") if item.strip()}
    assert "base-uri 'self'" in directives
    assert "object-src 'none'" in directives
    assert "frame-ancestors 'none'" in directives
    assert "form-action 'self'" in directives
    assert "script-src 'self'" in directives
    assert "connect-src 'self' https://generativelanguage.googleapis.com wss://generativelanguage.googleapis.com" in directives
    assert all("unsafe-inline" not in item for item in directives if item.startswith("script-src"))


def test_dockerfile_copies_all_runtime_python_modules():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for filename in (
        "manifest.py",
        "parser_layout.py",
        "session_service.py",
        "observability.py",
        "ocr_adapter.py",
    ):
        assert filename in dockerfile


def test_runtime_distribution_has_no_openai_provider_artifacts():
    assert "openai" not in (ROOT / "requirements-server.txt").read_text(encoding="utf-8").lower()
    assert not (ROOT / "document_compiler.py").exists()
    assert not (ROOT / "providers" / "openai_semantic_classifier.py").exists()
    assert not (ROOT / "providers" / "openai_semantic_compiler.py").exists()
