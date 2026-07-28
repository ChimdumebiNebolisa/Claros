"""Assignment loading, parsing, and export helpers."""
import logging
import os
import re
import hashlib
import hmac
import secrets
import tempfile
from pathlib import Path

import fitz
from fastapi import HTTPException
from fastapi.responses import Response

import config
import storage
from manifest import AssignmentManifest, build_manifest, parse_manifest_json
from storage import (
    assignment_pdf_path,
    delete_assignment_prefix,
    download_manifest_from_gcs,
    upload_manifest_to_gcs,
    upload_pdf_to_gcs,
)
from config import get_gcs_bucket
from exporter import SidePanelOverflowError, UnsupportedAnswerTextError, build_original_export_pdf
from document_pipeline import document_questions, parse_document
from parser import PDFProcessingError, parse_pdf_with_diagnostics
from semantic_classifier import GeminiSemanticClassifier, NullSemanticClassifier
from review_service import apply_review_actions
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


def create_assignment_capability() -> str:
    """Return a browser-held owner capability; persist only its keyed digest."""
    return secrets.token_urlsafe(32)


def assignment_capability_digest(capability: str) -> str:
    return hmac.new(
        config.get_session_hmac_secret().encode("utf-8"),
        capability.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def require_assignment_capability(assignment_id: str, capability: str | None) -> AssignmentManifest:
    """Authorize a sensitive assignment action without exposing capability state."""
    if not capability:
        raise HTTPException(status_code=403, detail="Assignment capability is required")
    manifest = load_assignment_manifest(assignment_id)
    stored = manifest.assignment_capability_hash or ""
    candidate = assignment_capability_digest(capability)
    if not stored or not hmac.compare_digest(stored, candidate):
        raise HTTPException(status_code=403, detail="Invalid assignment capability")
    return manifest


def _download_pdf_bytes(assignment_id: str) -> bytes:
    if storage.is_local_backend():
        return storage.download_pdf_bytes(assignment_id)
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


def _parse_and_build_manifest(
    assignment_id: str,
    pdf_path: str,
    *,
    review_mode: str = "direct",
    assignment_capability_hash: str | None = None,
) -> AssignmentManifest:
    if config.CLAROS_DEMO_MODE:
        from demo.hero_fixture import manifest_questions

        demo_pdf_bytes = Path(pdf_path).read_bytes()
        demo_questions = manifest_questions(demo_pdf_bytes)
        if demo_questions is not None:
            with fitz.open(pdf_path) as document:
                return build_manifest(
                    assignment_id=assignment_id,
                    title="River Habitat Investigation",
                    questions=demo_questions,
                    parse_status="ok",
                    parse_warnings=["offline_synthetic_semantic_fixture"],
                    page_count=document.page_count,
                    ttl_days=config.ASSIGNMENT_TTL_DAYS,
                    parser="offline-synthetic-fixture-v1",
                    review_mode=review_mode,
                    review_status="unreviewed",
                    assignment_capability_hash=assignment_capability_hash,
                )
    document_model = None
    parser_name = "legacy"
    if config.PDF_PARSER_MODE == "legacy":
        title, questions, warnings, parse_status = parse_pdf_with_diagnostics(pdf_path)
        payload = [
            {
                "id": q.id,
                "label": getattr(q, "label", None),
                "text": q.text,
                "page": q.page,
                "page_index": q.page - 1,
                "prompt_region": q.prompt_region,
                "answer_region": q.answer_region,
                "detected_answer_region": q.detected_answer_region,
                "layout_confidence": q.layout_confidence,
                "confidence": q.layout_confidence,
                "needs_layout_review": q.needs_layout_review,
                "review_status": "needs_review" if q.needs_layout_review else "auto_approved",
                "answer_region_status": "detected" if q.answer_region else "side_panel",
                "approved": not q.needs_layout_review and bool(q.answer_region),
            }
            for q in questions
        ]
    else:
        with open(pdf_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        if config.ENABLE_DOCUMENT_SEMANTICS and not config.ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS:
            logger.warning("Synchronous document semantics are disabled; run classification in a parser worker/service")
        classifier = NullSemanticClassifier()
        if config.ENABLE_DOCUMENT_SEMANTICS and config.ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS:
            if config.DOCUMENT_SEMANTIC_PROVIDER == "gemini":
                classifier = GeminiSemanticClassifier()
        try:
            document_model = parse_document(
                pdf_bytes,
                semantic_classifier=classifier,
                review_mode=review_mode,
                paddle_all_pages=config.PDF_PARSER_MODE == "paddle",
            )
        except fitz.FileDataError as exc:
            raise PDFProcessingError("PDF could not be opened") from exc
        parser_name = document_model.parser
        title = document_model.title
        payload = document_questions(document_model)
        warnings = document_model.warnings
        parse_status = {
            "parsed": "ok",
            "low_confidence": "layout_review_required",
            "requires_ocr": "requires_ocr",
            "failed": "failed",
        }[document_model.status.value]
    with fitz.open(pdf_path) as document:
        page_count = document.page_count
    return build_manifest(
        assignment_id=assignment_id,
        title=title,
        questions=payload,
        parse_status=parse_status,
        parse_warnings=warnings,
        page_count=page_count,
        ttl_days=config.ASSIGNMENT_TTL_DAYS,
        parser=parser_name,
        review_mode=review_mode,
        review_status="draft" if review_mode == "teacher" else "unreviewed",
        document=document_model,
        assignment_capability_hash=assignment_capability_hash,
    )


def persist_assignment_from_pdf_bytes(
    assignment_id: str,
    pdf_bytes: bytes,
    *,
    review_mode: str = "direct",
    assignment_capability_hash: str | None = None,
) -> AssignmentManifest:
    """Parse locally, upload PDF + manifest, or cleanup on failure."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        manifest = _parse_and_build_manifest(
            assignment_id,
            tmp_path,
            review_mode=review_mode,
            assignment_capability_hash=assignment_capability_hash,
        )
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
    return manifest.title, manifest.to_questions_dict(approved_only=manifest.review_mode == "teacher")


def load_assignment_pdf_bytes(assignment_id: str) -> bytes:
    """Return the original worksheet PDF after validating its manifest lifecycle."""
    load_assignment_manifest(assignment_id)
    return _download_pdf_bytes(assignment_id)


def render_assignment_page(assignment_id: str, page_number: int, scale: float = 1.5) -> bytes:
    """Render one original worksheet page to PNG for the browser document canvas."""
    pdf_bytes = load_assignment_pdf_bytes(assignment_id)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_number < 1 or page_number > document.page_count:
            raise ValueError("Page not found")
        pixmap = document[page_number - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()


def get_parse_diagnostics(assignment_id: str) -> dict:
    manifest = load_assignment_manifest(assignment_id)
    return {
        "assignment_id": assignment_id,
        "parse_status": manifest.parse_status,
        "parse_warnings": manifest.parse_warnings,
        "num_questions": len(manifest.questions),
        "question_ids": [q.id for q in manifest.questions],
        "page_count": manifest.page_count,
        "layout_review_question_ids": [
            q.id for q in manifest.questions if q.needs_layout_review
        ],
        "expires_at": manifest.expires_at,
        "parser": manifest.parser,
        "review_mode": manifest.review_mode,
        "review_status": manifest.review_status,
    }


def review_assignment(
    assignment_id: str,
    actions: list[dict],
    *,
    finalize: bool = False,
) -> AssignmentManifest:
    manifest = load_assignment_manifest(assignment_id)
    pdf_bytes = _download_pdf_bytes(assignment_id)
    updated = apply_review_actions(
        manifest,
        actions,
        pdf_bytes=pdf_bytes,
        finalize=finalize,
    )
    upload_manifest_to_gcs(assignment_id, updated.model_dump_json())
    return updated


def format_assignment_text(title: str, questions: list[dict]) -> str:
    return title + "\n\n" + "\n\n".join(
        f"Question {q.get('label') or q['id']}: {q['text']}" for q in questions
    )


def load_assignment_text_from_gcs(assignment_id: str) -> str:
    """Load assignment text for system prompt."""
    title, questions = load_assignment_from_gcs(assignment_id)
    return format_assignment_text(title, questions)


def load_export_source(assignment_id: str) -> tuple[list[dict], bytes]:
    """Load one immutable-in-process export snapshot for validation and rendering."""
    _title, questions = load_assignment_from_gcs(assignment_id)
    return questions, _download_pdf_bytes(assignment_id)


def build_export_response(
    assignment_id: str,
    answers_list: list[dict],
    *,
    questions: list[dict] | None = None,
    pdf_bytes: bytes | None = None,
) -> Response:
    """Build an export from either a supplied validated snapshot or a fresh source load."""
    try:
        if questions is None and pdf_bytes is None:
            questions, pdf_bytes = load_export_source(assignment_id)
        elif questions is None or pdf_bytes is None:
            raise ValueError("questions and pdf_bytes must be supplied together")
    except AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise HTTPException(status_code=404, detail="Assignment not found")
    except Exception:
        logger.exception("Failed to load assignment %s for export", assignment_id)
        raise HTTPException(status_code=500, detail="Could not load assignment for export.")
    try:
        pdf_bytes = build_original_export_pdf(pdf_bytes, questions, answers_list)
    except SidePanelOverflowError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "SIDE_PANEL_OVERFLOW", "affected_task_ids": exc.affected_task_ids},
        )
    except UnsupportedAnswerTextError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "UNSUPPORTED_ANSWER_TEXT", "affected_question_ids": exc.affected_question_ids},
        )
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
