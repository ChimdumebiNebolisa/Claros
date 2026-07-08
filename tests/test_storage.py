"""Storage helper tests."""
from unittest.mock import MagicMock

import storage


def test_assignment_pdf_path_uses_canonical_filename():
    assignment_id = "550e8400-e29b-41d4-a716-446655440000"
    assert storage.assignment_pdf_path(assignment_id) == (
        f"assignments/{assignment_id}/{storage.CANONICAL_PDF_NAME}"
    )


def test_upload_pdf_to_gcs_uploads_canonical_blob(monkeypatch):
    bucket = MagicMock()
    blob = MagicMock()
    bucket.blob.return_value = blob
    bucket.name = "claros-bucket"
    monkeypatch.setattr(storage, "get_gcs_bucket", lambda: bucket)

    path = storage.upload_pdf_to_gcs("550e8400-e29b-41d4-a716-446655440000", b"%PDF-1.4")

    bucket.blob.assert_called_once_with(
        "assignments/550e8400-e29b-41d4-a716-446655440000/assignment.pdf"
    )
    blob.upload_from_string.assert_called_once_with(b"%PDF-1.4", content_type="application/pdf")
    assert path.endswith("/assignments/550e8400-e29b-41d4-a716-446655440000/assignment.pdf")
