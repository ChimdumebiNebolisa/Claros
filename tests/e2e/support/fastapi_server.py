"""Serve the built Claros application for deterministic browser acceptance."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from backend.config import Settings
from backend.main import create_app


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    port = int(_required_environment("CLAROS_E2E_PORT"))
    if not 1 <= port <= 65_535:
        raise RuntimeError("CLAROS_E2E_PORT must be a valid TCP port")

    dist_path = Path(_required_environment("CLAROS_E2E_DIST_PATH")).resolve()
    if not (dist_path / "index.html").is_file():
        raise RuntimeError("Build the E2E Vite application before starting FastAPI")

    storage_path = Path(_required_environment("CLAROS_E2E_STORAGE_PATH")).resolve()
    qpdf_path = Path(_required_environment("CLAROS_E2E_QPDF_PATH")).resolve()
    if not qpdf_path.is_file():
        raise RuntimeError("CLAROS_E2E_QPDF_PATH must identify the verified qpdf executable")

    settings = Settings(
        _env_file=None,
        environment="test",
        storage_backend="local",
        local_storage_path=storage_path,
        public_origin=f"http://127.0.0.1:{port}",
        owner_cookie_name="claros_e2e_owner",
        cookie_secret="e2e-browser-owner-secret-with-sufficient-entropy",  # noqa: S106
        review_token_secret="e2e-browser-review-secret-with-sufficient-entropy",  # noqa: S106
        upload_rate_limit=100,
        realtime_rate_limit=100,
        semantic_engine="current",
        realtime_engine="current",
        pdf_engine="openpdf",
        openpdf_qpdf_path=qpdf_path,
    )
    app = create_app(settings=settings, dist_path=dist_path)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        workers=1,
        access_log=False,
        server_header=False,
        proxy_headers=False,
        timeout_keep_alive=5,
    )


if __name__ == "__main__":
    main()
