"""Google Cloud Storage helpers for assignment PDFs."""
from config import get_gcs_bucket

CANONICAL_PDF_NAME = "assignment.pdf"


def assignment_pdf_path(assignment_id: str) -> str:
    return f"assignments/{assignment_id}/{CANONICAL_PDF_NAME}"


def upload_pdf_to_gcs(assignment_id: str, pdf_bytes: bytes) -> str:
    """Upload PDF to GCS at assignments/{assignment_id}/assignment.pdf. Returns gs:// path."""
    bucket = get_gcs_bucket()
    blob_path = assignment_pdf_path(assignment_id)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    return f"gs://{bucket.name}/{blob_path}"
