"""Google Cloud Storage helpers for assignment PDFs, manifests, and sessions."""
from google.api_core.exceptions import PreconditionFailed

from config import get_gcs_bucket
from manifest import CANONICAL_MANIFEST_NAME
from observability import record_metric
CANONICAL_PDF_NAME = "assignment.pdf"
SESSION_PREFIX = "sessions/"


class StorageConflict(RuntimeError):
    """Raised when a conditional object write loses a concurrent update race."""


def assignment_pdf_path(assignment_id: str) -> str:
    return f"assignments/{assignment_id}/{CANONICAL_PDF_NAME}"


def assignment_manifest_path(assignment_id: str) -> str:
    return f"assignments/{assignment_id}/{CANONICAL_MANIFEST_NAME}"


def session_blob_path(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}.json"


def assignment_prefix(assignment_id: str) -> str:
    return f"assignments/{assignment_id}/"


def upload_pdf_to_gcs(assignment_id: str, pdf_bytes: bytes) -> str:
    """Upload PDF to GCS at assignments/{assignment_id}/assignment.pdf. Returns gs:// path."""
    bucket = get_gcs_bucket()
    blob_path = assignment_pdf_path(assignment_id)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    return f"gs://{bucket.name}/{blob_path}"


def upload_manifest_to_gcs(assignment_id: str, manifest_json: str) -> str:
    bucket = get_gcs_bucket()
    blob_path = assignment_manifest_path(assignment_id)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(manifest_json.encode("utf-8"), content_type="application/json")
    return f"gs://{bucket.name}/{blob_path}"


def download_manifest_from_gcs(assignment_id: str) -> bytes | None:
    bucket = get_gcs_bucket()
    blob = bucket.blob(assignment_manifest_path(assignment_id))
    if not blob.exists():
        return None
    return blob.download_as_bytes()


def delete_assignment_prefix(assignment_id: str) -> None:
    bucket = get_gcs_bucket()
    prefix = assignment_prefix(assignment_id)
    blobs = list(bucket.list_blobs(prefix=prefix))
    for blob in blobs:
        blob.delete()


def upload_session_to_gcs(
    session_id: str,
    payload: bytes,
    if_generation_match: int | None = None,
    *,
    return_generation: bool = False,
) -> str | tuple[str, int | None]:
    bucket = get_gcs_bucket()
    blob_path = session_blob_path(session_id)
    blob = bucket.blob(blob_path)
    try:
        kwargs = {"content_type": "application/json"}
        if if_generation_match is not None:
            kwargs["if_generation_match"] = if_generation_match
        blob.upload_from_string(payload, **kwargs)
    except PreconditionFailed as exc:
        record_metric("write_conflict", status="conflict", reason="storage")
        raise StorageConflict(f"Session changed concurrently: {session_id}") from exc
    path = f"gs://{bucket.name}/{blob_path}"
    if return_generation:
        return path, getattr(blob, "generation", None)
    return path


def download_session_from_gcs(session_id: str, *, with_generation: bool = False) -> bytes | tuple[bytes, int | None]:
    bucket = get_gcs_bucket()
    blob = bucket.blob(session_blob_path(session_id))
    if not blob.exists():
        raise ValueError(f"Session not found: {session_id}")
    payload = blob.download_as_bytes()
    if with_generation:
        return payload, getattr(blob, "generation", None)
    return payload


def delete_session_from_gcs(session_id: str) -> None:
    bucket = get_gcs_bucket()
    blob = bucket.blob(session_blob_path(session_id))
    if blob.exists():
        blob.delete()


def delete_assignment_and_sessions(assignment_id: str) -> None:
    delete_assignment_prefix(assignment_id)
