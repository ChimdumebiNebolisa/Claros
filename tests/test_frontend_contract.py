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


def test_landing_is_light_flat_and_uses_real_workspace_states():
    html = _read("landing.html")
    css = _read("styles/landing.css")

    assert html.count('href="/app?sample=canonical-short-answer-ecosystems"') == 1
    assert 'src="/sample-workspace-review.png"' in html
    assert 'src="/sample-workspace.png"' in html
    assert "rotate(" not in css
    assert "linear-gradient(" not in css
    assert "background: var(--bg)" in css
