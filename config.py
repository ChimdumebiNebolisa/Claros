"""Environment and shared configuration."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_env_path = ROOT / ".env"
if _env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_path)

LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


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
