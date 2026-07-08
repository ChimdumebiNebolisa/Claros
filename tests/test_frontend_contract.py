"""Frontend static contract tests executed via pytest."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_frontend_contract_script_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_frontend.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_landing_and_app_reference_shared_tokens():
    landing = (ROOT / "frontend" / "landing.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    assert 'href="/styles/tokens.css"' in landing
    assert 'href="/styles/tokens.css"' in app
