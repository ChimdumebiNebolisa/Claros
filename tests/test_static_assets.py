"""Additional static route and asset coverage."""
from pathlib import Path

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


def test_dockerfile_copies_all_runtime_python_modules():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for filename in ("manifest.py", "parser_layout.py", "session_service.py", "observability.py"):
        assert filename in dockerfile
