"""Assignment loading, parsing, and export helpers."""
import logging
import os
import re
import tempfile

from fastapi import HTTPException
from fastapi.responses import Response

import config
from manifest import AssignmentManifest, build_manifest, parse_manifest_json
from storage import (
    assignment_pdf_path,
    delete_assignment_prefix,
    download_manifest_from_gcs,
    upload_manifest_to_gcs,
    upload_pdf_to_gcs,
)
from config import get_gcs_bucket
from exporter import build_export_pdf
from parser import parse_pdf_with_diagnostics
from observability import record_metric

logger = logging.getLogger(__name__)


class AssignmentExpiredError(RuntimeError):
    """Raised when a persisted assignment is past its configured retention window."""


def _ensure_manifest_active(manifest: AssignmentManifest) -> AssignmentManifest:
    if manifest.is_expired():
        record_metric("session_expired", status="expired")
        raise AssignmentExpiredError("Assignment expired")
    return manifest


def _export_filename(assignment_id: str) -> str:
    safe_id = re.sub(r"[^0-9a-fA-F-]", "", assignment_id)
    return f"claros-{safe_id or 'assignment'}.pdf"


def _download_pdf_bytes(assignment_id: str) -> bytes:
    bucket = get_gcs_bucket()
    canonical_blob = bucket.blob(assignment_pdf_path(assignment_id))
    if canonical_blob.exists():
        return canonical_blob.download_as_bytes()
    prefix = f"assignments/{assignment_id}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    pdf_blobs = [b for b in blobs if b.name.lower().endswith(".pdf")]
    if not pdf_blobs:
        raise ValueError(f"No PDF found for assignment {assignment_id}")
    pdf_blobs.sort(key=lambda b: b.name)
    return pdf_blobs[0].download_as_bytes()


def _parse_and_build_manifest(assignment_id: str, pdf_path: str) -> AssignmentManifest:
    title, questions, warnings, parse_status = parse_pdf_with_diagnostics(pdf_path)
    payload = [{"id": q.id, "text": q.text} for q in questions]
    return build_manifest(
        assignment_id=assignment_id,
        title=title,
        questions=payload,
        parse_status=parse_status,
        parse_warnings=warnings,
        ttl_days=config.ASSIGNMENT_TTL_DAYS,
    )


def persist_assignment_from_pdf_bytes(assignment_id: str, pdf_bytes: bytes) -> AssignmentManifest:
    """Parse locally, upload PDF + manifest, or cleanup on failure."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        manifest = _parse_and_build_manifest(assignment_id, tmp_path)
        upload_pdf_to_gcs(assignment_id, pdf_bytes)
        upload_manifest_to_gcs(assignment_id, manifest.model_dump_json())
        return manifest
    except Exception:
        try:
            delete_assignment_prefix(assignment_id)
        except Exception:
            logger.exception("Failed to cleanup assignment prefix after upload error %s", assignment_id)
        raise
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def load_assignment_manifest(assignment_id: str) -> AssignmentManifest:
    """Load manifest from GCS; backfill by parsing PDF once for legacy assignments."""
    if config.USE_MANIFEST:
        raw = download_manifest_from_gcs(assignment_id)
        if raw:
            return _ensure_manifest_active(parse_manifest_json(raw))

    pdf_bytes = _download_pdf_bytes(assignment_id)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        manifest = _parse_and_build_manifest(assignment_id, tmp_path)
        try:
            upload_manifest_to_gcs(assignment_id, manifest.model_dump_json())
        except Exception:
            logger.exception("Manifest backfill upload failed for %s", assignment_id)
        return _ensure_manifest_active(manifest)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def load_assignment_from_gcs(assignment_id: str) -> tuple[str, list]:
    """Load assignment title and questions, preferring persisted manifest."""
    manifest = load_assignment_manifest(assignment_id)
    return manifest.title, manifest.to_questions_dict()


def get_parse_diagnostics(assignment_id: str) -> dict:
    manifest = load_assignment_manifest(assignment_id)
    return {
        "assignment_id": assignment_id,
        "parse_status": manifest.parse_status,
        "parse_warnings": manifest.parse_warnings,
        "num_questions": len(manifest.questions),
        "question_ids": [q.id for q in manifest.questions],
        "expires_at": manifest.expires_at,
    }


def format_assignment_text(title: str, questions: list[dict]) -> str:
    return title + "\n\n" + "\n\n".join(
        f"Question {q['id']}: {q['text']}" for q in questions
    )


def load_assignment_text_from_gcs(assignment_id: str) -> str:
    """Load assignment text for system prompt."""
    title, questions = load_assignment_from_gcs(assignment_id)
    return format_assignment_text(title, questions)


def build_export_response(assignment_id: str, answers_list: list[dict]) -> Response:
    try:
        title, questions = load_assignment_from_gcs(assignment_id)
    except AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise HTTPException(status_code=404, detail="Assignment not found")
    except Exception:
        logger.exception("Failed to load assignment %s for export", assignment_id)
        raise HTTPException(status_code=500, detail="Could not load assignment for export.")
    pdf_bytes = build_export_pdf(title, questions, answers_list)
    record_metric("export", status="ok")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(assignment_id)}"'},
    )


def delete_assignment(assignment_id: str) -> None:
    try:
        _download_pdf_bytes(assignment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Assignment not found")
    delete_assignment_prefix(assignment_id)
