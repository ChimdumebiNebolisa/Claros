#!/usr/bin/env python3
"""Static contract checks for Claros frontend entrypoints and shared assets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _require(source: str, needles: tuple[str, ...], filename: str) -> None:
    for needle in needles:
        if needle not in source:
            raise AssertionError(f"{filename} missing expected content: {needle!r}")


def validate_shared_styles() -> None:
    tokens = _read(FRONTEND / "styles" / "tokens.css")
    _require(
        tokens,
        (
            "@font-face",
            '"Instrument Sans"',
            "--iris: #2864f0",
            "--ink: #172033",
            "--bg: #f7f8fa",
            "--radius-sm: 8px",
            "--radius-md: 12px",
        ),
        "tokens.css",
    )


def validate_landing_html() -> None:
    html = _read(FRONTEND / "landing.html")
    app_source = _read(ROOT / "marketing" / "src" / "App.tsx")
    preview_source = _read(
        ROOT / "marketing" / "src" / "components" / "product-preview.tsx"
    )
    landing_css = _read(ROOT / "marketing" / "src" / "index.css")
    components = _read(ROOT / "marketing" / "components.json")
    _require(
        html,
        (
            'href="/styles/landing.css"',
            'src="/landing-app.js"',
            'id="root"',
        ),
        "landing.html",
    )
    _require(
        app_source,
        (
            'href="/app"',
            'href="/app?sample=canonical-short-answer-ecosystems"',
            "The pause is part of the product",
            "Ready does not mean written",
            "Confirmed, not written",
            "Safety and access",
            "does not promise automatic timed deletion",
            'id="how-it-works"',
            'id="safety"',
            'id="faq"',
            "<ProductPreview />",
            "Accordion",
        ),
        "marketing/src/App.tsx",
    )
    _require(
        preview_source,
        (
            'from "@/components/ui/card"',
            'from "@/components/ui/tabs"',
            'from "@/components/ui/textarea"',
            "Interactive example",
            "Confirming does not write to the worksheet",
            "Confirmed, not written",
            "Add to export",
        ),
        "marketing/src/components/product-preview.tsx",
    )
    if app_source.count('href="/app?sample=canonical-short-answer-ecosystems"') != 1:
        raise AssertionError("landing source must expose one primary sample action")
    if '"style": "radix-nova"' not in components:
        raise AssertionError("landing must retain its initialized Shadcn design system")
    bundle = FRONTEND / "landing-app.js"
    if not bundle.exists() or bundle.stat().st_size < 50_000:
        raise AssertionError("compiled landing-app.js is missing or unexpectedly small")
    for source_name, source in (
        ("landing source", app_source + preview_source),
        ("landing CSS source", landing_css),
    ):
        for forbidden in (
            "sample-workspace-review.png",
            "sample-workspace.png",
            "rotate(",
            "linear-gradient(",
            "\u2014",
            "\u2013",
        ):
            if forbidden in source:
                raise AssertionError(
                    f"{source_name} contains obsolete or prohibited content: {forbidden!r}"
                )


def validate_app_html() -> None:
    html = _read(FRONTEND / "app.html")
    _require(
        html,
        (
            'href="/styles/tokens.css"',
            'href="/styles/app.css"',
            'id="uploadBtn"',
            'id="sampleChooser"',
            'id="sessionPanel"',
            'id="documentViewport"',
            'id="documentWorkspace"',
            'id="mobileViewSwitch"',
            'id="worksheetViewBtn"',
            'id="answerViewBtn"',
            'aria-controls="documentWorkspace"',
            'aria-controls="sessionPanel"',
            'id="draftEditor"',
            'id="answerConfirmation"',
            'id="writeConfirmation"',
            'id="writtenStatus"',
            'id="writtenAnswer"',
            'id="typeInsteadBtn"',
            'id="writeConfirmedAnswerBtn"',
            'id="responseTargets"',
            'id="workspaceStatus"',
            "/session-rules.js",
            "/voice-product-bridge.js",
            "/voice-live-transport.js",
            "/ui-state.js",
            "/worksheet-view.js",
            "/app.js",
        ),
        "app.html",
    )
    for obsolete in (
        'id="rejectAnswerBtn"',
        'id="returnToWorksheetBtn"',
        "teacherReviewMode",
        "layoutReviewPanel",
        "confirmRegionBtn",
    ):
        if obsolete in html:
            raise AssertionError(f"student app retains obsolete control: {obsolete!r}")

    app_css = _read(FRONTEND / "styles" / "app.css")
    mobile_start = app_css.rfind("@media (max-width: 700px)")
    mobile_css = app_css[mobile_start:] if mobile_start >= 0 else ""
    _require(
        mobile_css,
        (
            'body[data-mobile-view="worksheet"] .session-panel',
            'body[data-mobile-view="answer"] .document-workspace',
            "position: static",
            "width: 100%",
        ),
        "app.css mobile contract",
    )
    if "grid-template-columns: minmax(0, 2fr) minmax(22rem, 1fr)" not in app_css:
        raise AssertionError("desktop workspace must keep an approximately two-thirds document column")


def validate_app_js_contract() -> None:
    js = _read(FRONTEND / "app.js")
    _require(
        js,
        (
            "ClarosSessionRules",
            "ClarosUiState",
            "ClarosWorksheetView",
            "ClarosVoiceProductBridge",
            "ClarosVoiceLiveTransport",
            "applyVoiceProductEvents",
            "scheduleVoiceReconnect",
            "interruptProvider",
            "/api/write/",
            "/api/session/",
            "reauthorize-write",
            "confirmProposedAnswer",
            "writeConfirmedAnswerBtn",
            "setWorkspaceState",
            "setVoiceState",
            "setMobileView",
            "dataset.mobileView",
            "renderResponseState",
            "writeFailure",
            "loadSamplePdf",
            "/api/samples",
            "X-Assignment-Capability",
            "task_id",
            "response_region_id",
            "defaultResponseTarget",
            "method: 'DELETE'",
        ),
        "app.js",
    )
    if "await triggerWrite" in js[js.find("async function confirmProposedAnswer"):js.find("async function triggerWrite")]:
        raise AssertionError("answer confirmation must not automatically trigger a write")
    for forbidden in ("teacherReviewMode", "layout_confirmed", "answer_region: question.answer_region"):
        if forbidden in js:
            raise AssertionError(f"student app contains prohibited client authority: {forbidden!r}")


def validate_modules() -> None:
    expectations = {
        "session-rules.js": "ClarosSessionRules",
        "voice-product-bridge.js": "ClarosVoiceProductBridge",
        "voice-live-transport.js": "ClarosVoiceLiveTransport",
        "ui-state.js": "getResponseModel",
        "worksheet-view.js": "ClarosWorksheetView",
    }
    for filename, marker in expectations.items():
        source = _read(FRONTEND / filename)
        if marker not in source:
            raise AssertionError(f"{filename} missing expected module marker: {marker!r}")
    worksheet = _read(FRONTEND / "worksheet-view.js")
    for forbidden in ("setCorrectionMode", "confirmSelected", "Number(state.activeQuestionId)"):
        if forbidden in worksheet:
            raise AssertionError(f"worksheet-view.js exposes prohibited geometry/identity behavior: {forbidden!r}")


def main() -> int:
    validators = (
        validate_shared_styles,
        validate_landing_html,
        validate_app_html,
        validate_app_js_contract,
        validate_modules,
    )
    for validator in validators:
        validator()
        print(f"ok: {validator.__name__}")
    print("frontend contract validation passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"frontend contract validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
