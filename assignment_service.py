"""Assignment loading, parsing, and export helpers."""
import logging
import os
import re
import tempfile

from fastapi import HTTPException
from fastapi.responses import Response

from storage import assignment_pdf_path
from config import get_gcs_bucket
from exporter import build_export_pdf
from parser import parse_pdf

logger = logging.getLogger(__name__)


def _export_filename(assignment_id: str) -> str:
    safe_id = re.sub(r"[^0-9a-fA-F-]", "", assignment_id)
    return f"claros-{safe_id or 'assignment'}.pdf"


def load_assignment_from_gcs(assignment_id: str) -> tuple[str, list]:
    """Load PDF from GCS, parse, return (title, questions) where questions = [{"id": n, "text": "..."}]."""
    bucket = get_gcs_bucket()
    canonical_blob = bucket.blob(assignment_pdf_path(assignment_id))
    if canonical_blob.exists():
        pdf_bytes = canonical_blob.download_as_bytes()
    else:
        prefix = f"assignments/{assignment_id}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        pdf_blobs = [b for b in blobs if b.name.lower().endswith(".pdf")]
        if not pdf_blobs:
            raise ValueError(f"No PDF found for assignment {assignment_id}")
        pdf_blobs.sort(key=lambda b: b.name)
        pdf_bytes = pdf_blobs[0].download_as_bytes()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        title, questions = parse_pdf(tmp_path)
        return title, [{"id": q.id, "text": q.text} for q in questions]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def format_assignment_text(title: str, questions: list[dict]) -> str:
    return title + "\n\n" + "\n\n".join(
        f"Question {q['id']}: {q['text']}" for q in questions
    )


def load_assignment_text_from_gcs(assignment_id: str) -> str:
    """Load PDF from GCS, parse, return assignment text for system prompt."""
    title, questions = load_assignment_from_gcs(assignment_id)
    return format_assignment_text(title, questions)


def build_export_response(assignment_id: str, answers_list: list[dict]) -> Response:
    try:
        title, questions = load_assignment_from_gcs(assignment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Assignment not found")
    except Exception:
        logger.exception("Failed to load assignment %s for export", assignment_id)
        raise HTTPException(status_code=500, detail="Could not load assignment for export.")
    pdf_bytes = build_export_pdf(title, questions, answers_list)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(assignment_id)}"'},
    )
