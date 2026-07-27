"""Production session-secret configuration tests."""
import os
import subprocess
import sys


def test_production_startup_rejects_missing_session_hmac_secret():
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["GCS_BUCKET_NAME"] = "claros-test-bucket"
    env.pop("SESSION_HMAC_SECRET", None)
    result = subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "SESSION_HMAC_SECRET must be set" in result.stderr
