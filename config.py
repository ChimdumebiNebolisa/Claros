"""Environment and shared configuration."""
import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent

_env_path = ROOT / ".env"
if _env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_path)

_claros_env = os.environ.get("CLAROS_ENV", "").strip().lower()
_app_env = os.environ.get("APP_ENV", "").strip().lower()
if _claros_env and _app_env and _claros_env != _app_env:
    raise RuntimeError("CLAROS_ENV and APP_ENV must not conflict")
APP_ENV = _claros_env or _app_env or "development"
_EPHEMERAL_SESSION_HMAC_SECRET = secrets.token_urlsafe(48)

LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

_DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
_DEFAULT_MAX_CONVERSATION_TURNS = 400  # hard validation cap
_DEFAULT_CONVERSATION_TRIM_TURNS = 200  # soft cap sent to Gemini (keeps most recent)
_DEFAULT_MAX_PDF_PAGES = 100
_DEFAULT_MAX_EXTRACTED_TEXT_CHARS = 500_000
_DEFAULT_MAX_UPLOADS_PER_MINUTE = 6 if APP_ENV in {"production", "prod"} else 60
_DEFAULT_MAX_PROVIDER_SESSIONS_PER_MINUTE = 20 if APP_ENV in {"production", "prod"} else 120
_DEFAULT_MAX_WRITES_PER_MINUTE = 30 if APP_ENV in {"production", "prod"} else 180
_DEFAULT_MAX_MUTATIONS_PER_MINUTE = 30 if APP_ENV in {"production", "prod"} else 180
_DEFAULT_MAX_SESSION_STARTS_PER_MINUTE = 30 if APP_ENV in {"production", "prod"} else 180
_DEFAULT_MAX_PAGE_RENDERS_PER_MINUTE = 120 if APP_ENV in {"production", "prod"} else 600
_DEFAULT_MAX_CONCURRENT_UPLOADS = 2
_DEFAULT_PREVIEW_DPI = 120
_DEFAULT_MAX_PREVIEW_DPI = 200
_DEFAULT_PADDLEOCR_DPI = 150
_DEFAULT_PADDLEOCR_CPU_THREADS = 4


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
MAX_UPLOADS_PER_MINUTE = _int_env("MAX_UPLOADS_PER_MINUTE", _DEFAULT_MAX_UPLOADS_PER_MINUTE)
MAX_PROVIDER_SESSIONS_PER_MINUTE = _int_env(
    "MAX_PROVIDER_SESSIONS_PER_MINUTE", _DEFAULT_MAX_PROVIDER_SESSIONS_PER_MINUTE
)
MAX_WRITES_PER_MINUTE = _int_env("MAX_WRITES_PER_MINUTE", _DEFAULT_MAX_WRITES_PER_MINUTE)
MAX_MUTATIONS_PER_MINUTE = _int_env("MAX_MUTATIONS_PER_MINUTE", _DEFAULT_MAX_MUTATIONS_PER_MINUTE)
MAX_SESSION_STARTS_PER_MINUTE = _int_env(
    "MAX_SESSION_STARTS_PER_MINUTE", _DEFAULT_MAX_SESSION_STARTS_PER_MINUTE
)
MAX_PAGE_RENDERS_PER_MINUTE = _int_env("MAX_PAGE_RENDERS_PER_MINUTE", _DEFAULT_MAX_PAGE_RENDERS_PER_MINUTE)
MAX_CONCURRENT_UPLOADS = _int_env("MAX_CONCURRENT_UPLOADS", _DEFAULT_MAX_CONCURRENT_UPLOADS)
PREVIEW_DPI = _int_env("PREVIEW_DPI", _DEFAULT_PREVIEW_DPI)
MAX_PREVIEW_DPI = _int_env("MAX_PREVIEW_DPI", _DEFAULT_MAX_PREVIEW_DPI)
PADDLEOCR_DPI = _int_env("PADDLEOCR_DPI", _DEFAULT_PADDLEOCR_DPI)
PADDLEOCR_CPU_THREADS = _int_env("PADDLEOCR_CPU_THREADS", _DEFAULT_PADDLEOCR_CPU_THREADS)
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
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return key.strip()


def get_gcs_bucket():
    bucket_name = os.environ.get("GCS_BUCKET_NAME", "").strip()
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET_NAME not set in .env")
    from google.cloud import storage

    client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return client.bucket(bucket_name)


def get_text_model() -> str:
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash").strip()
    if not model:
        raise RuntimeError("GEMINI_TEXT_MODEL must be configured")
    if not model.startswith("gemini-"):
        raise RuntimeError("GEMINI_TEXT_MODEL must name a Gemini model")
    return model


def is_production() -> bool:
    return APP_ENV in {"production", "prod"}


def is_debug_gemini_enabled() -> bool:
    return (
        not is_production()
        and os.environ.get("ENABLE_DEBUG_GEMINI", "").strip().lower() in ("1", "true", "yes")
    )


def is_debug_routes_enabled() -> bool:
    return (
        not is_production()
        and os.environ.get("ENABLE_DEBUG_ROUTES", "").strip().lower() in ("1", "true", "yes")
    )


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
ENABLE_OCR = _bool_env("ENABLE_OCR", False)
ENABLE_PADDLEOCR = _bool_env("ENABLE_PADDLEOCR", False)
ALLOW_SYNCHRONOUS_PADDLEOCR = _bool_env("ALLOW_SYNCHRONOUS_PADDLEOCR", False)
ENABLE_DOCUMENT_SEMANTICS = _bool_env("ENABLE_DOCUMENT_SEMANTICS", True)
ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS = _bool_env("ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS", True)
# Promotion gate: semantic confidence alone is not sufficient until the corpus
# demonstrates acceptable task precision and answer-region accuracy.
ENABLE_DOCUMENT_TASK_AUTO_APPROVE = _bool_env("ENABLE_DOCUMENT_TASK_AUTO_APPROVE", False)
CLAROS_DEMO_MODE = _bool_env("CLAROS_DEMO_MODE", False)
STORAGE_BACKEND = os.environ.get(
    "CLAROS_STORAGE_BACKEND", "local" if CLAROS_DEMO_MODE else "gcs"
).strip().lower()
LOCAL_STORAGE_DIR = os.environ.get("CLAROS_LOCAL_STORAGE_DIR", ".claros-data").strip() or ".claros-data"
if STORAGE_BACKEND not in {"local", "gcs"}:
    raise RuntimeError("CLAROS_STORAGE_BACKEND must be 'local' or 'gcs'")
if is_production() and STORAGE_BACKEND != "gcs":
    raise RuntimeError("Production requires CLAROS_STORAGE_BACKEND=gcs")
if is_production() and not os.environ.get("GCS_BUCKET_NAME", "").strip():
    raise RuntimeError("GCS_BUCKET_NAME must be set when APP_ENV=production")
DOCUMENT_SEMANTIC_PROVIDER = os.environ.get("DOCUMENT_SEMANTIC_PROVIDER", "gemini").strip().lower()
if DOCUMENT_SEMANTIC_PROVIDER not in {"gemini", "none"}:
    raise RuntimeError("DOCUMENT_SEMANTIC_PROVIDER must be 'gemini' or 'none'")
PDF_PARSER_MODE = os.environ.get("PDF_PARSER_MODE", "hybrid").strip().lower()
if PDF_PARSER_MODE not in {"legacy", "paddle", "hybrid"}:
    logger.warning("Invalid PDF_PARSER_MODE=%r; using legacy", PDF_PARSER_MODE)
    PDF_PARSER_MODE = "legacy"
PADDLEOCR_MIN_CONFIDENCE = 0.55
TASK_AUTO_APPROVE_CONFIDENCE = 0.90
ANSWER_REGION_AUTO_APPROVE_CONFIDENCE = 0.90


def get_session_hmac_secret() -> str:
    secret = os.environ.get("SESSION_HMAC_SECRET", "").strip()
    if secret:
        return secret
    if is_production():
        raise RuntimeError("SESSION_HMAC_SECRET must be set when APP_ENV=production")
    logger.warning("SESSION_HMAC_SECRET is unset; using an ephemeral development secret")
    return _EPHEMERAL_SESSION_HMAC_SECRET


if is_production() and not os.environ.get("SESSION_HMAC_SECRET", "").strip():
    raise RuntimeError("SESSION_HMAC_SECRET must be set when APP_ENV=production")

if is_production():
    get_api_key()
    get_text_model()
