"""Additional static route and asset coverage."""
from fastapi.testclient import TestClient

import main as main_module

client = TestClient(main_module.app)


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


def test_debug_gemini_disabled_by_default():
    response = client.get("/debug-gemini")
    assert response.status_code == 404
