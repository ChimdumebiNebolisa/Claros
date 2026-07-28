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


def test_production_startup_rejects_missing_gemini_credentials():
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["GCS_BUCKET_NAME"] = "claros-test-bucket"
    env["SESSION_HMAC_SECRET"] = "test-session-hmac-secret"
    env["GEMINI_API_KEY"] = ""
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
    assert "GEMINI_API_KEY is not configured" in result.stderr


def test_invalid_semantic_provider_fails_instead_of_falling_back():
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["DOCUMENT_SEMANTIC_PROVIDER"] = "openai"
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
    assert "DOCUMENT_SEMANTIC_PROVIDER must be 'gemini' or 'none'" in result.stderr


def test_conflicting_environment_names_fail_closed():
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["CLAROS_ENV"] = "development"
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
    assert "CLAROS_ENV and APP_ENV must not conflict" in result.stderr


def test_production_startup_rejects_non_gemini_text_model():
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["GCS_BUCKET_NAME"] = "claros-test-bucket"
    env["SESSION_HMAC_SECRET"] = "test-session-hmac-secret"
    env["GEMINI_API_KEY"] = "test-key"
    env["GEMINI_TEXT_MODEL"] = "other-provider-model"
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
    assert "GEMINI_TEXT_MODEL must name a Gemini model" in result.stderr


def test_production_hides_interactive_api_documentation():
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["GCS_BUCKET_NAME"] = "claros-test-bucket"
    env["SESSION_HMAC_SECRET"] = "test-session-hmac-secret"
    env["GEMINI_API_KEY"] = "test-key"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from fastapi.testclient import TestClient; import main; print(TestClient(main.app).get('/docs').status_code)",
        ],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("404")
