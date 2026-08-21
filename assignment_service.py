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
from manifest import (
    AssignmentManifest,
    build_manifest,
    parse_manifest_json,
    sign_assignment_manifest,
    verify_assignment_manifest,
)
from storage import (
    assignment_pdf_path,
    delete_assignment_and_sessions,
    delete_assignment_prefix,
    download_manifest_from_gcs,
    upload_manifest_to_gcs,
    upload_pdf_to_gcs,
)
from config import get_gcs_bucket
from exporter import (
    SidePanelOverflowError,
    UnsupportedAnswerTextError,
    build_canonical_export_pdf,
    build_original_export_pdf,
)
from document_pipeline import (
    _page_extraction_dimensions,
    _page_requires_display_transform,
    document_questions,
    parse_supported_worksheet,
)
from parser import PDFProcessingError
from semantic_classifier import GeminiSemanticClassifier, NullSemanticClassifier
from review_service import apply_review_actions
from observability import record_metric

logger = logging.getLogger(__name__)


class AssignmentExpiredError(RuntimeError):
    """Raised when a persisted assignment is past its configured retention window."""


class AssignmentSourceMismatchError(ValueError):
    """Raised when canonical physical evidence no longer matches its PDF."""


class AssignmentManifestIntegrityError(ValueError):
    """Raised when a persisted canonical manifest fails its server MAC."""


def _ensure_manifest_active(manifest: AssignmentManifest) -> AssignmentManifest:
    if manifest.is_expired():
        record_metric("assignment_expired", status="expired")
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


def _has_physical_response_targets(manifest: AssignmentManifest) -> bool:
    """Detect canonical response evidence that can be shown or approved later."""
    return any(task.response_links for task in manifest.document.tasks)


def _is_unsigned_legacy_quarantine(
    assignment_id: str,
    manifest: AssignmentManifest,
) -> bool:
    """Accept only the no-authority historical manifest shape without a MAC."""
    document = manifest.document
    return (
        manifest.assignment_id == assignment_id
        and manifest.assignment_capability_hash is None
        and not document.blocks
        and not document.response_regions
        and all(page.coordinate_space.value == "normalized_legacy" and page.needs_review for page in document.pages)
        and all(
            task.evidence_status.value == "legacy_unverified"
            and not task.prompt_block_ids
            and not task.response_links
            and task.side_panel_fallback
            for task in document.tasks
        )
    )


def _signed_manifest(assignment_id: str, manifest: AssignmentManifest) -> AssignmentManifest:
    """Authenticate the exact persisted canonical record for its storage key."""
    return sign_assignment_manifest(
        manifest,
        expected_assignment_id=assignment_id,
        key=config.get_assignment_manifest_hmac_key(),
    )


def _verify_loaded_manifest(assignment_id: str, manifest: AssignmentManifest) -> AssignmentManifest:
    """Reject altered canonical targets while retaining old side-panel records."""
    if manifest.integrity_hmac is not None:
        if not verify_assignment_manifest(
            manifest,
            expected_assignment_id=assignment_id,
            key=config.get_assignment_manifest_hmac_key(),
        ):
            raise AssignmentManifestIntegrityError("Assignment manifest integrity check failed")
    elif not _is_unsigned_legacy_quarantine(assignment_id, manifest):
        # An unsigned record is permitted only for a fully quarantined legacy
        # document with no capability binding, source blocks, regions, or
        # response links. Anything else can influence a live assignment and
        # therefore requires a server integrity tag.
        raise AssignmentManifestIntegrityError("Unsigned manifest is not a quarantined legacy record")
    return manifest


def ensure_manifest_source_matches_pdf(
    manifest: AssignmentManifest,
    pdf_bytes: bytes,
) -> None:
    """Reject a changed worksheet before exposing canonical physical geometry."""
    if not _has_physical_response_targets(manifest):
        return
    expected = manifest.document.source_sha256
    actual = hashlib.sha256(pdf_bytes).hexdigest()
    if not expected or not hmac.compare_digest(expected, actual):
        raise AssignmentSourceMismatchError("Worksheet source does not match its canonical physical evidence")
    try:
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    except fitz.FileDataError as exc:
        raise AssignmentSourceMismatchError("Worksheet source is not a readable PDF") from exc
    try:
        if pdf.page_count != len(manifest.document.pages):
            raise AssignmentSourceMismatchError("Worksheet source does not match its canonical physical evidence")
        for canonical_page in manifest.document.pages:
            page = pdf[canonical_page.page_index]
            width_points, height_points = _page_extraction_dimensions(page)
            if (
                abs(canonical_page.width_points - width_points) > 0.5
                or abs(canonical_page.height_points - height_points) > 0.5
                or canonical_page.rotation != page.rotation
                or canonical_page.display_transform_required != _page_requires_display_transform(page)
            ):
                raise AssignmentSourceMismatchError("Worksheet source does not match its canonical physical evidence")
    finally:
        pdf.close()


def load_assignment_manifest_for_client(assignment_id: str) -> AssignmentManifest:
    """Load a manifest only after binding any physical targets to its PDF."""
    manifest = load_assignment_manifest(assignment_id)
    if _has_physical_response_targets(manifest):
        ensure_manifest_source_matches_pdf(manifest, _download_pdf_bytes(assignment_id))
    return manifest


def _parse_and_build_manifest(
    assignment_id: str,
    pdf_path: str,
    *,
    review_mode: str = "direct",
    assignment_capability_hash: str | None = None,
) -> AssignmentManifest:
    with open(pdf_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()
    if config.ENABLE_DOCUMENT_SEMANTICS and not config.ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS:
        logger.warning("Synchronous document semantics are disabled; supported uploads will reject")
    classifier = NullSemanticClassifier()
    if config.ENABLE_DOCUMENT_SEMANTICS and config.ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS:
        if config.DOCUMENT_SEMANTIC_PROVIDER == "gemini":
            classifier = GeminiSemanticClassifier()
    try:
        document_model = parse_supported_worksheet(
            pdf_bytes,
            semantic_classifier=classifier,
            paddle_all_pages=config.PDF_PARSER_MODE == "paddle",
        )
    except fitz.FileDataError as exc:
        raise PDFProcessingError("PDF could not be opened") from exc
    parser_name = document_model.parser
    title = document_model.title
    payload = document_questions(document_model)
    warnings = document_model.warnings
    parse_status = "ok"
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
        manifest = _signed_manifest(assignment_id, manifest)
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
    """Load manifest from GCS; parse PDF for legacy assignments without capability binding.

    Stage 11: never persist a signed serving manifest without an owner capability
    hash. Capability-less backfill returns an in-memory parse only.
    """
    if config.USE_MANIFEST:
        raw = download_manifest_from_gcs(assignment_id)
        if raw:
            return _ensure_manifest_active(_verify_loaded_manifest(assignment_id, parse_manifest_json(raw)))

    pdf_bytes = _download_pdf_bytes(assignment_id)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        # In-memory only — uploading a capability-less signed MAC bricks ownership.
        return _ensure_manifest_active(_parse_and_build_manifest(assignment_id, tmp_path))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def delete_assignment(assignment_id: str) -> None:
    """Delete assignment PDF/manifest/session markers when any of them remain."""
    has_pdf = True
    try:
        _download_pdf_bytes(assignment_id)
    except ValueError:
        has_pdf = False
    has_manifest = False
    if config.USE_MANIFEST:
        try:
            has_manifest = bool(download_manifest_from_gcs(assignment_id))
        except Exception:
            has_manifest = False
    has_sessions = bool(storage.list_assignment_session_ids(assignment_id))
    if not has_pdf and not has_manifest and not has_sessions:
        raise HTTPException(status_code=404, detail="Assignment not found")
    delete_assignment_and_sessions(assignment_id)


def load_assignment_from_gcs(assignment_id: str) -> tuple[str, list]:
    """Load assignment title and questions, preferring persisted manifest."""
    manifest = load_assignment_manifest(assignment_id)
    return manifest.title, manifest.to_questions_dict(approved_only=manifest.review_mode == "teacher")


def load_assignment_pdf_bytes(assignment_id: str) -> bytes:
    """Return the original worksheet PDF after validating its manifest lifecycle."""
    manifest = load_assignment_manifest(assignment_id)
    pdf_bytes = _download_pdf_bytes(assignment_id)
    ensure_manifest_source_matches_pdf(manifest, pdf_bytes)
    return pdf_bytes


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
        "layout_review_question_ids": [q.id for q in manifest.questions if q.needs_layout_review],
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
    ensure_manifest_source_matches_pdf(manifest, pdf_bytes)
    updated = apply_review_actions(
        manifest,
        actions,
        pdf_bytes=pdf_bytes,
        finalize=finalize,
    )
    updated = _signed_manifest(assignment_id, updated)
    upload_manifest_to_gcs(assignment_id, updated.model_dump_json())
    return updated


def format_assignment_text(title: str, questions: list[dict]) -> str:
    return title + "\n\n" + "\n\n".join(f"Question {q.get('label') or q['id']}: {q['text']}" for q in questions)


def load_assignment_text_from_gcs(assignment_id: str) -> str:
    """Load assignment text for system prompt."""
    title, questions = load_assignment_from_gcs(assignment_id)
    return format_assignment_text(title, questions)


def load_export_source(assignment_id: str) -> tuple[list[dict], bytes]:
    """Load one immutable-in-process export snapshot for validation and rendering."""
    _title, questions = load_assignment_from_gcs(assignment_id)
    return questions, _download_pdf_bytes(assignment_id)


def load_canonical_export_source(assignment_id: str) -> tuple[AssignmentManifest, bytes]:
    """Load one manifest/PDF snapshot for canonical target-based export."""
    manifest = load_assignment_manifest(assignment_id)
    return manifest, _download_pdf_bytes(assignment_id)


def build_export_response(
    assignment_id: str,
    answers_list: list[dict],
    *,
    questions: list[dict] | None = None,
    pdf_bytes: bytes | None = None,
    manifest: AssignmentManifest | None = None,
) -> Response:
    """Build an export from either a supplied validated snapshot or a fresh source load."""
    try:
        if manifest is not None:
            if pdf_bytes is None:
                raise ValueError("manifest and pdf_bytes must be supplied together")
        elif questions is None and pdf_bytes is None:
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
        if manifest is not None:
            pdf_bytes = build_canonical_export_pdf(pdf_bytes, manifest.document, answers_list)
        else:
            pdf_bytes = build_original_export_pdf(pdf_bytes, questions or [], answers_list)
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
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Export target changed. Reload and confirm again.") from exc
    record_metric("export", status="ok")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(assignment_id)}"'},
    )
