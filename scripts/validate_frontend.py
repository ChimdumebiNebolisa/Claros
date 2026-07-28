#!/usr/bin/env python3
"""Static contract checks for Claros frontend entrypoints and shared assets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

REQUIRED_STYLES = ("tokens.css", "landing.css", "app.css")
REQUIRED_SCRIPTS = (
    "app.js",
    "session-rules.js",
    "voice-product-bridge.js",
    "voice-live-transport.js",
    "ui-state.js",
    "worksheet-view.js",
)
LEGACY_FRONTEND_FILES = ()
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
        "Keep the page in view",
        "Typed works throughout",
        "/app?sample=canonical-short-answer-ecosystems",
        "Short Answer · Choice · Math",
        'class="hero-brand"',
        ">Claros</p>",
        "/samples/canonical-short-answer-ecosystems/preview.png",
        "evidence-caption",
    )
    for needle in checks:
        if needle not in html:
            raise AssertionError(f"landing.html missing expected content: {needle!r}")
    if "evidence-note" in html:
        raise AssertionError("landing hero must not use floating evidence-note overlays")
    if 'src="/sample-workspace.png"' in html:
        raise AssertionError("landing hero must use an official sample preview, not the synthetic workspace asset")


def validate_app_html() -> None:
    html = _read(FRONTEND / "app.html")
    checks = (
        'href="/styles/tokens.css"',
        'href="/styles/app.css"',
        'id="uploadBtn"',
        'id="uploadZone"',
        'id="sampleChooser"',
        'id="sampleChooserActions"',
        'data-sample-id="canonical-short-answer-ecosystems"',
        'data-sample-id="canonical-choice-digital-safety"',
        'data-sample-id="canonical-numeric-everyday-math"',
        'id="sessionPanel"',
        'id="fileInput"',
        'id="keyboardFallback"',
        'id="workspaceErrors"',
        'id="semanticTaskBlock"',
        'id="documentViewport"',
        'id="answerConfirmation"',
        'id="writeConfirmation"',
        'id="writeConfirmedAnswerBtn"',
        'id="placementSummary"',
        'id="taskChoices"',
        'id="answerProgress"',
        'id="layoutReviewNotice"',
        'id="confirmedAnswerPreview"',
        'id="returnToWorksheetBtn"',
        'id="micBtn"',
        'id="interruptBtn"',
        'id="voiceBadge"',
        'id="typedAnswer"',
        'id="responseTargets"',
        'id="currentResponseLabel"',
        'id="workspaceStatus"',
        'id="pageImage"',
        'aria-pressed="true"',
        'class="sr-only"',
        'document-page-surface',
        "/app.js",
        "/session-rules.js",
        "/voice-product-bridge.js",
        "/voice-live-transport.js",
        "/ui-state.js",
        "/worksheet-view.js",
    )
    for needle in checks:
        if needle not in html:
            raise AssertionError(f"app.html missing expected content: {needle!r}")
    if "teacherReviewMode" in html or "teacherReviewPanel" in html:
        raise AssertionError("student app must not expose teacher review controls")
    if "layoutReviewPanel" in html or "confirmRegionBtn" in html:
        raise AssertionError("student app must not expose client-side layout approval controls")
    app_css = _read(FRONTEND / "styles" / "app.css")
    if "min-width: 34rem" in app_css or "min-width: 30rem" in app_css:
        raise AssertionError("document page must not force a desktop min-width that breaks mobile fit-width")
    mobile_block_start = app_css.find("@media (max-width: 760px)")
    mobile_block = app_css[mobile_block_start:] if mobile_block_start >= 0 else ""
    required_tokens = (
        ":not(.question-context)",
        ":not(.notice)",
        ":not(.keyboard-fallback)",
        "padding-bottom: max(24rem, 52dvh",
        "padding-bottom: 4.4rem",
    )
    if not all(token in mobile_block for token in required_tokens):
        raise AssertionError(
            "collapsed mobile dock must keep typed answer / notice / keyboard fallback visible "
            "and reserve worksheet clearance under the fixed sheet"
        )


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
        "ClarosUiState",
        "ClarosWorksheetView",
        "ClarosVoiceProductBridge",
        "ClarosVoiceLiveTransport",
        "applyVoiceProductEvents",
        "scheduleVoiceReconnect",
        "handleProviderDisconnect",
        "suppressPlaybackUntilTurnComplete",
        "interruptProvider",
        "MAX_VOICE_RECONNECT_ATTEMPTS",
        "/api/write/",
        "/api/session-config/",
        "/api/session/start",
        "/api/session/",
        "reauthorize-write",
        "reauthorizeWriteToken",
        "confirmProposedAnswer",
        "writeConfirmedAnswerBtn",
        "setWorkspaceState",
        "setVoiceState",
        "showVoiceFallback",
        "setSessionPanelExpanded",
        "applyTypedDraft",
        "workspaceErrors",
        "clearAssignmentSessionState",
        "loadSamplePdf",
        "/api/samples",
        "X-Assignment-Capability",
        "task_id",
        "response_region_id",
        "defaultResponseTarget",
        "write_token",
        "activeTaskId",
        "activeResponseRegionId",
        "renderTaskChoices",
        "task-choice-btn",
        "renderAnswerProgress",
        "confirmedAnswerPreview",
        "layoutReviewNotice",
        "canonical-short-answer-ecosystems",
    )
    for needle in checks:
        if needle not in js:
            raise AssertionError(f"app.js missing expected content: {needle!r}")
    if "await triggerWrite(questionId);" in js:
        raise AssertionError("answer confirmation must not automatically trigger a write")
    if "teacherReviewMode" in js or "teacherReviewPanel" in js:
        raise AssertionError("student app must not include teacher review branches")
    if "layout_confirmed" in js or "answer_region: question.answer_region" in js:
        raise AssertionError("student writes must not submit browser-supplied geometry")
    if "responseTargetIds[0]" in js:
        raise AssertionError("app defaults must resolve the server-selected response target")
    if "responseState.draft || full" in js:
        raise AssertionError("write-intent must not propose the full utterance when no draft exists")
    if "processorNode.connect(audioContext.destination)" in js:
        raise AssertionError("mic capture must live in voice-live-transport, not app.js speaker monitor path")


def validate_session_rules() -> None:
    js = _read(FRONTEND / "session-rules.js")
    if "ClarosSessionRules" not in js:
        raise AssertionError("session-rules.js must export ClarosSessionRules")


def validate_voice_product_bridge() -> None:
    js = _read(FRONTEND / "voice-product-bridge.js")
    if "ClarosVoiceProductBridge" not in js:
        raise AssertionError("voice-product-bridge.js must export ClarosVoiceProductBridge")
    if "interpretUserTurn" not in js or "interpretClarosTurn" not in js:
        raise AssertionError("voice-product-bridge.js must expose turn interpreters")
    if "needs_answer_before_write" not in js:
        raise AssertionError("write intent without a draft must emit needs_answer_before_write")


def validate_voice_live_transport() -> None:
    js = _read(FRONTEND / "voice-live-transport.js")
    if "ClarosVoiceLiveTransport" not in js:
        raise AssertionError("voice-live-transport.js must export ClarosVoiceLiveTransport")
    if "interruptProvider" not in js or "activityEnd" not in js:
        raise AssertionError("voice transport must support provider interrupt via activityEnd")
    if "silentGain" not in js:
        raise AssertionError("voice capture must not monitor mic audio into speakers")


def validate_worksheet_view() -> None:
    js = _read(FRONTEND / "worksheet-view.js")
    if "ClarosWorksheetView" not in js:
        raise AssertionError("worksheet-view.js must export ClarosWorksheetView")
    if "/pages/" not in js:
        raise AssertionError("worksheet-view.js must load assignment page PNG routes")
    if "X-Assignment-Capability" not in js or "fetch(requestUrl" not in js:
        raise AssertionError("worksheet-view.js must fetch protected page PNGs with assignment capability")
    if "setCorrectionMode" in js or "confirmSelected" in js or "function adjust" in js:
        raise AssertionError("worksheet-view.js must not let students alter answer geometry")
    if "normalizeDocument" not in js or "response_region_id" not in js:
        raise AssertionError("worksheet-view.js must normalize canonical task and response-region data")
    if "onSelectTarget" not in js or "dataset.responseRegionId" not in js:
        raise AssertionError("worksheet-view.js must select response targets by stable IDs")
    if "defaultResponseTargetId" not in js or "choiceById" not in js:
        raise AssertionError("worksheet-view.js must preserve canonical defaults and explicit choice mappings")
    if "Number(state.activeQuestionId)" in js:
        raise AssertionError("worksheet-view.js must not use numeric question identity")
    if "location needs review; writing is unavailable" not in js:
        raise AssertionError("worksheet regions must announce unsafe placement")
    if "fitWidthMode" not in js or "preserveFit" not in js:
        raise AssertionError("worksheet-view.js must implement true fit-width mode distinct from manual zoom")
    if "function fitWidth() {\n      setZoom(100);\n    }" in js.replace("\r\n", "\n"):
        raise AssertionError("fitWidth must not be a no-op alias that ignores container scaling contracts")


def validate_ui_state() -> None:
    js = _read(FRONTEND / "ui-state.js")
    if "ClarosUiState" not in js:
        raise AssertionError("ui-state.js must export ClarosUiState")
    if "WORKSPACE_STATES" not in js or "VOICE_STATES" not in js:
        raise AssertionError("ui-state.js must declare WORKSPACE_STATES and VOICE_STATES")


def main() -> int:
    validators = (
        validate_shared_styles,
        validate_landing_html,
        validate_app_html,
        validate_legacy_frontend_files,
        validate_app_js_contract,
        validate_session_rules,
        validate_voice_product_bridge,
        validate_voice_live_transport,
        validate_worksheet_view,
        validate_ui_state,
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
