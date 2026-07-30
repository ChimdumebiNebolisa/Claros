"""Regression contracts for the simplified Claros frontend."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def _read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_mobile_view_switch_is_explicit_and_obsolete_mobile_controls_are_gone():
    html = _read("app.html")
    js = _read("app.js")
    css = _read("styles/app.css")

    assert 'id="worksheetViewBtn"' in html
    assert 'id="answerViewBtn"' in html
    assert 'aria-controls="documentWorkspace"' in html
    assert 'aria-controls="sessionPanel"' in html
    assert 'id="returnToWorksheetBtn"' not in html
    assert 'id="rejectAnswerBtn"' not in html
    assert "setMobileView('worksheet')" in js
    assert "setMobileView('answer')" in js
    assert 'body[data-mobile-view="worksheet"] .session-panel' in css
    assert 'body[data-mobile-view="answer"] .document-workspace' in css


def test_response_states_keep_confirmation_and_write_separate():
    html = _read("app.html")
    js = _read("app.js")

    assert 'id="draftEditor"' in html
    assert 'id="answerConfirmation"' in html
    assert 'id="writeConfirmation"' in html
    assert 'id="writtenStatus"' in html
    assert "Confirmed, not written" in html
    confirm_body = js.split("async function confirmProposedAnswer()", 1)[1].split(
        "async function triggerWrite", 1
    )[0]
    assert "/confirm" in confirm_body
    assert "/api/write/" not in confirm_body
    assert "responseState.confirmed = false" in js
    assert "Review and confirm the exact answer again." in js


def test_landing_uses_shadcn_live_states_instead_of_workspace_images():
    html = _read("landing.html")
    app = (ROOT / "marketing" / "src" / "App.tsx").read_text(encoding="utf-8")
    preview = (
        ROOT / "marketing" / "src" / "components" / "product-preview.tsx"
    ).read_text(encoding="utf-8")
    css = (ROOT / "marketing" / "src" / "index.css").read_text(encoding="utf-8")
    components = (ROOT / "marketing" / "components.json").read_text(encoding="utf-8")

    assert app.count('href="/app?sample=canonical-short-answer-ecosystems"') == 1
    assert 'src="/landing-app.js"' in html
    assert "<ProductPreview />" in app
    assert 'from "@/components/ui/tabs"' in preview
    assert 'from "@/components/ui/card"' in preview
    assert "Confirmed, not written" in preview
    assert '"style": "radix-nova"' in components
    assert "sample-workspace-review.png" not in app + preview
    assert "sample-workspace.png" not in app + preview
    assert "rotate(" not in css
    assert "linear-gradient(" not in css
    assert "\u2014" not in app + preview
    assert "\u2013" not in app + preview
    assert "--primary: oklch(0.55 0.205 259)" in css
