"""Environment and shared configuration."""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent

_env_path = ROOT / ".env"
if _env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_path)

LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

_DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
_DEFAULT_MAX_CONVERSATION_TURNS = 400  # hard validation cap
_DEFAULT_CONVERSATION_TRIM_TURNS = 200  # soft cap sent to Gemini (keeps most recent)
_DEFAULT_MAX_PDF_PAGES = 100
_DEFAULT_MAX_EXTRACTED_TEXT_CHARS = 500_000
_DEFAULT_PREVIEW_DPI = 120
_DEFAULT_MAX_PREVIEW_DPI = 200


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError("must be positive")
        return value
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


MAX_UPLOAD_BYTES = _int_env("MAX_UPLOAD_BYTES", _DEFAULT_MAX_UPLOAD_BYTES)
MAX_CONVERSATION_TURNS = _int_env("MAX_CONVERSATION_TURNS", _DEFAULT_MAX_CONVERSATION_TURNS)
CONVERSATION_TRIM_TURNS = _int_env("CONVERSATION_TRIM_TURNS", _DEFAULT_CONVERSATION_TRIM_TURNS)
MAX_PDF_PAGES = _int_env("MAX_PDF_PAGES", _DEFAULT_MAX_PDF_PAGES)
MAX_EXTRACTED_TEXT_CHARS = _int_env("MAX_EXTRACTED_TEXT_CHARS", _DEFAULT_MAX_EXTRACTED_TEXT_CHARS)
PREVIEW_DPI = _int_env("PREVIEW_DPI", _DEFAULT_PREVIEW_DPI)
MAX_PREVIEW_DPI = _int_env("MAX_PREVIEW_DPI", _DEFAULT_MAX_PREVIEW_DPI)
PDF_MAGIC = b"%PDF"


def looks_like_pdf(content: bytes) -> bool:
    """Return True when bytes look like a PDF after stripping common leading noise."""
    if not content:
        return False
    stripped = content.lstrip(b"\x00\xff\xfe\x00\xef\xbb\xbf \t\r\n")
    return stripped.startswith(PDF_MAGIC)


def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not key.strip():
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return key.strip()


def get_gcs_bucket():
    bucket_name = os.environ.get("GCS_BUCKET_NAME", "").strip()
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET_NAME not set in .env")
    from google.cloud import storage

    client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return client.bucket(bucket_name)


def get_text_model() -> str:
    return os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash").strip()


def is_debug_gemini_enabled() -> bool:
    return os.environ.get("ENABLE_DEBUG_GEMINI", "").strip().lower() in ("1", "true", "yes")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes")


_DEFAULT_SESSION_TTL_HOURS = 48
_DEFAULT_ASSIGNMENT_TTL_DAYS = 90

SESSION_TTL_HOURS = _int_env("SESSION_TTL_HOURS", _DEFAULT_SESSION_TTL_HOURS)
ASSIGNMENT_TTL_DAYS = _int_env("ASSIGNMENT_TTL_DAYS", _DEFAULT_ASSIGNMENT_TTL_DAYS)
USE_MANIFEST = _bool_env("USE_MANIFEST", True)
ENFORCE_WRITE_CONTRACT = _bool_env("ENFORCE_WRITE_CONTRACT", True)
ENABLE_OCR = _bool_env("ENABLE_OCR", False)


def get_session_hmac_secret() -> str:
    secret = os.environ.get("SESSION_HMAC_SECRET", "").strip()
    if secret:
        return secret
    # Dev fallback only; production should set SESSION_HMAC_SECRET explicitly.
    return "claros-dev-session-hmac-change-me"
