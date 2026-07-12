#!/usr/bin/env python3
"""Static contract checks for Claros frontend entrypoints and shared assets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

REQUIRED_STYLES = ("tokens.css", "landing.css", "app.css")
REQUIRED_SCRIPTS = ("app.js", "session-rules.js")
LEGACY_FRONTEND_FILES = ("index.html",)
LEGACY_MARKER = "LEGACY"


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def validate_shared_styles() -> None:
    tokens = _read(FRONTEND / "styles" / "tokens.css")
    if "--iris:" not in tokens or "--ink:" not in tokens:
        raise AssertionError("tokens.css must define core design tokens (--iris, --ink)")


def validate_landing_html() -> None:
    html = _read(FRONTEND / "landing.html")
    checks = (
        'href="/styles/tokens.css"',
        'href="/styles/landing.css"',
        'href="/app"',
        "Built for students",
    )
    for needle in checks:
        if needle not in html:
            raise AssertionError(f"landing.html missing expected content: {needle!r}")


def validate_app_html() -> None:
    html = _read(FRONTEND / "app.html")
    checks = (
        'href="/styles/tokens.css"',
        'href="/styles/app.css"',
        'id="uploadBtn"',
        'id="uploadZone"',
        'id="sessionPanel"',
        'id="fileInput"',
        'id="keyboardFallback"',
        "/app.js",
        "/session-rules.js",
    )
    for needle in checks:
        if needle not in html:
            raise AssertionError(f"app.html missing expected content: {needle!r}")


def validate_legacy_frontend_files() -> None:
    for filename in LEGACY_FRONTEND_FILES:
        html = _read(FRONTEND / filename)
        if LEGACY_MARKER not in html[:300] or "NOT SERVED" not in html[:300]:
            raise AssertionError(f"{filename} must keep an explicit legacy/not-served marker while present")


def validate_app_js_contract() -> None:
    js = _read(FRONTEND / "app.js")
    checks = (
        "getElementById('uploadBtn')",
        "getElementById('sessionPanel')",
        "ClarosSessionRules",
        "/api/write/",
        "/api/session-config/",
        "/api/session/start",
        "btn-confirm-answer",
        "confirmAnswerForQuestion",
        "showKeyboardFallback",
    )
    for needle in checks:
        if needle not in js:
            raise AssertionError(f"app.js missing expected content: {needle!r}")


def validate_session_rules() -> None:
    js = _read(FRONTEND / "session-rules.js")
    if "ClarosSessionRules" not in js:
        raise AssertionError("session-rules.js must export ClarosSessionRules")


def main() -> int:
    validators = (
        validate_shared_styles,
        validate_landing_html,
        validate_app_html,
        validate_legacy_frontend_files,
        validate_app_js_contract,
        validate_session_rules,
    )
    for fn in validators:
        fn()
        print(f"ok: {fn.__name__}")
    print("frontend contract validation passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"frontend contract validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
