"""Google Cloud Storage helpers for assignment PDFs, manifests, and sessions."""
from config import get_gcs_bucket
from manifest import CANONICAL_MANIFEST_NAME
CANONICAL_PDF_NAME = "assignment.pdf"
SESSION_PREFIX = "sessions/"


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


def upload_session_to_gcs(session_id: str, payload: bytes) -> str:
    bucket = get_gcs_bucket()
    blob_path = session_blob_path(session_id)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(payload, content_type="application/json")
    return f"gs://{bucket.name}/{blob_path}"


def download_session_from_gcs(session_id: str) -> bytes:
    bucket = get_gcs_bucket()
    blob = bucket.blob(session_blob_path(session_id))
    if not blob.exists():
        raise ValueError(f"Session not found: {session_id}")
    return blob.download_as_bytes()


def delete_session_from_gcs(session_id: str) -> None:
    bucket = get_gcs_bucket()
    blob = bucket.blob(session_blob_path(session_id))
    if blob.exists():
        blob.delete()


def delete_assignment_and_sessions(assignment_id: str) -> None:
    delete_assignment_prefix(assignment_id)
