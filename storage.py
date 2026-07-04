"""Google Cloud Storage helpers for assignment PDFs."""
from config import get_gcs_bucket


def upload_pdf_to_gcs(assignment_id: str, pdf_bytes: bytes, filename: str = "assignment.pdf") -> str:
    """Upload PDF to GCS at assignments/{assignment_id}/{filename}. Returns gs:// path."""
    bucket = get_gcs_bucket()
    blob = bucket.blob(f"assignments/{assignment_id}/{filename}")
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    return f"gs://{bucket.name}/assignments/{assignment_id}/{filename}"
