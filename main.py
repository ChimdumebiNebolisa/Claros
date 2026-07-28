"""
Claros backend: FastAPI app with PDF upload, session config (ephemeral token), and write/export.
Real-time voice uses Gemini Live directly from the browser.
"""
import asyncio
import json
import logging
import uuid
from uuid import UUID

import fitz
from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

import assignment_service
from assignment_service import (
    build_export_response,
    delete_assignment,
    get_parse_diagnostics,
    load_canonical_export_source,
    persist_assignment_from_pdf_bytes,
    render_assignment_page,
    review_assignment,
)
import config
from gemini_service import create_session_config, debug_gemini_text_call, stamp_confirmed_answer
from schemas import (
    ExportRequest,
    SessionConfirmRequest,
    SessionRestoreRequest,
    SessionStartRequest,
    TeacherReviewRequest,
    WriteRequest,
)
import session_service
import storage
from observability import record_metric
from parser import PDFProcessingError
from rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

app = FastAPI(
    docs_url=None if config.is_production() else "/docs",
    redoc_url=None if config.is_production() else "/redoc",
    openapi_url=None if config.is_production() else "/openapi.json",
)
rate_limiter = SlidingWindowRateLimiter()
upload_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_UPLOADS)

# Worksheet response overlays set their physical geometry through element.style.
# Keep this narrow temporary style allowance until geometry moves to CSS classes.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' blob:; "
    "font-src 'self'; "
    "connect-src 'self' https://generativelanguage.googleapis.com wss://generativelanguage.googleapis.com"
)


@app.middleware("http")
async def limit_upload_concurrency(request: Request, call_next):
    if request.url.path != "/upload":
        return await call_next(request)
    try:
        await asyncio.wait_for(upload_semaphore.acquire(), timeout=0.1)
    except TimeoutError:
        return JSONResponse(
            status_code=429,
            content={"detail": "Upload capacity is temporarily full. Please retry shortly."},
        )
    try:
        return await call_next(request)
    finally:
        upload_semaphore.release()


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", _CONTENT_SECURITY_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), payment=(), usb=(), microphone=(self)")
    return response


@app.exception_handler(storage.StorageConflict)
async def storage_conflict_handler(_request, _exc):
    record_metric("write_conflict", status="conflict", reason="storage")
    return JSONResponse(
        status_code=409,
        content={"code": "SESSION_WRITE_CONFLICT", "detail": "Session changed. Refresh and try again."},
    )


@app.get("/health")
def health():
    """Lightweight container health endpoint with no external service dependency.

    Note: Cloud Run reserves paths ending in "z" (e.g. "/healthz"); the Google
    Front End intercepts them and returns 404 before the request reaches the
    container, so this endpoint must not end in "z".
    """
    return {"status": "ok"}


def _assignment_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Assignment not found")


def _require_assignment_capability(assignment_id: str, capability: str | None) -> None:
    """Require the browser-held assignment capability for sensitive resources."""
    try:
        assignment_service.require_assignment_capability(assignment_id, capability)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()


def _rate_limit_key(request: Request, capability: str | None = None) -> str:
    if capability:
        return f"capability:{assignment_service.assignment_capability_digest(capability)}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def _enforce_rate_limit(request: Request, bucket: str, limit: int, capability: str | None = None) -> None:
    if not rate_limiter.allow(f"{bucket}:{_rate_limit_key(request, capability)}", limit):
        record_metric("rate_limit", status="blocked", reason=bucket)
        raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload body in chunks so oversize files fail before buffering the full payload."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="File exceeds maximum upload size.")
        chunks.append(chunk)
    return b"".join(chunks)


@app.get("/api/session-config/{assignment_id}")
def get_session_config(
    assignment_id: UUID,
    request: Request,
    x_assignment_capability: str | None = Header(default=None),
):
    """Return ephemeral token + system prompt + model for browser-side Gemini Live. API key stays on server."""
    aid = str(assignment_id)
    _require_assignment_capability(aid, x_assignment_capability)
    _enforce_rate_limit(request, "provider_session", config.MAX_PROVIDER_SESSIONS_PER_MINUTE, x_assignment_capability)
    try:
        return create_session_config(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except assignment_service.AssignmentSourceMismatchError:
        raise HTTPException(status_code=409, detail="Worksheet source changed. Reload or re-upload it.")
    except ValueError:
        raise _assignment_not_found()
    except RuntimeError as e:
        if "token" in str(e).lower():
            raise HTTPException(status_code=500, detail="Session setup failed. Please try again.")
        raise HTTPException(status_code=500, detail="Session setup failed. Please try again.")
    except Exception:
        logger.exception("session-config failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Session setup failed. Please try again.")


@app.post("/api/session/start")
def start_tutoring_session(
    body: SessionStartRequest,
    request: Request,
    x_assignment_capability: str | None = Header(default=None),
):
    """Create a durable server-side session for an assignment."""
    aid = body.assignment_id.strip()
    try:
        _ = UUID(aid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assignment_id")
    _require_assignment_capability(aid, x_assignment_capability)
    _enforce_rate_limit(
        request,
        "session_start",
        config.MAX_SESSION_STARTS_PER_MINUTE,
        x_assignment_capability,
    )
    try:
        manifest = assignment_service.load_assignment_manifest_for_client(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except assignment_service.AssignmentSourceMismatchError:
        raise HTTPException(status_code=409, detail="Worksheet source changed. Reload or re-upload it.")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("session start load failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Could not load assignment. Please try again.")
    tasks = manifest.to_questions_dict(approved_only=manifest.review_mode == "teacher")
    payload = session_service.create_session(aid, tasks)
    record_metric("session_created", status="ok")
    payload["title"] = manifest.title
    # ``document`` is the versioned client-facing canonical contract.  The
    # questions projection is retained briefly for migration-only clients.
    payload["document"] = manifest.to_client_document(approved_only=manifest.review_mode == "teacher")
    payload["tasks"] = tasks
    payload["questions"] = tasks
    return payload


@app.post("/api/session/{session_id}/confirm")
def confirm_answer_for_question(
    session_id: UUID,
    body: SessionConfirmRequest,
    x_assignment_capability: str | None = Header(default=None),
):
    """Explicitly confirm a student-owned answer and receive a single-use write token."""
    state = session_service.load_session(str(session_id))
    _require_assignment_capability(state.assignment_id, x_assignment_capability)
    result = session_service.confirm_answer(
        str(session_id),
        body.session_secret,
        task_id=body.task_id,
        response_region_id=body.response_region_id,
        question_id=body.question_id,
        answer_text=body.answer_text,
    )
    record_metric("confirmation", status="ok")
    return result


@app.post("/api/session/{session_id}/restore")
def restore_session(
    session_id: UUID,
    body: SessionRestoreRequest,
    x_assignment_capability: str | None = Header(default=None),
):
    """Restore confirmed-answer state after a browser refresh."""
    state = session_service.load_session(str(session_id))
    _require_assignment_capability(state.assignment_id, x_assignment_capability)
    return session_service.restore_session_for_client(str(session_id), body.session_secret)


@app.post("/api/write/{assignment_id}")
async def write_confirmed_answer(
    assignment_id: UUID,
    body: WriteRequest,
    request: Request,
    x_assignment_capability: str | None = Header(default=None),
):
    """Write only the exact answer already confirmed for this assignment task."""
    aid = str(assignment_id)
    _require_assignment_capability(aid, x_assignment_capability)
    _enforce_rate_limit(request, "write", config.MAX_WRITES_PER_MINUTE, x_assignment_capability)
    if not body.answer_candidate.strip():
        raise HTTPException(status_code=400, detail="answer_candidate must be non-empty")
    if not body.write_token or not body.session_id or not body.session_secret:
        raise HTTPException(status_code=403, detail="Confirmed write_token and session credentials are required")
    state = session_service.load_session(body.session_id)
    if state.assignment_id != aid:
        raise HTTPException(status_code=403, detail="Session does not match assignment")
    if not state.verify_session_secret(body.session_secret):
        raise HTTPException(status_code=403, detail="Invalid session credentials")
    try:
        manifest = assignment_service.load_assignment_manifest(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("write load failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Could not load assignment. Please try again.")
    tasks = manifest.to_questions_dict(approved_only=manifest.review_mode == "teacher")
    task_id = state.resolve_task_id(body.task_id, body.question_id)
    response_region_id = body.response_region_id or state.default_response_region_id(task_id)
    question = next((task for task in tasks if task.get("task_id") == task_id), None)
    if question is None:
        raise HTTPException(status_code=409, detail="Task changed since confirmation. Reload and confirm again.")
    # The canonical target determines physical placement or side-panel fallback.
    # Client geometry is rejected at schema validation and never reaches this route.
    session_service.validate_task_snapshot(state, task_id, response_region_id, question)
    session_service.validate_write_token(
        state, task_id, response_region_id, body.answer_candidate, body.write_token
    )
    session_service.mark_answer_written(
        state, task_id, response_region_id, body.answer_candidate, question
    )
    return StreamingResponse(
        stamp_confirmed_answer(body.answer_candidate),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/export/{assignment_id}")
async def export_assignment_get(assignment_id: UUID):
    """Legacy query-string export is disabled to prevent answer injection."""
    raise HTTPException(status_code=405, detail="Use the authorized POST export flow")


@app.post("/export/{assignment_id}")
async def export_assignment_post(
    assignment_id: UUID,
    body: ExportRequest,
    x_assignment_capability: str | None = Header(default=None),
):
    """Export only answers written through the confirmed server-side flow."""
    aid = str(assignment_id)
    _require_assignment_capability(aid, x_assignment_capability)
    try:
        manifest, pdf_bytes = load_canonical_export_source(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("export load failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Could not load assignment. Please try again.")
    tasks = manifest.to_questions_dict(approved_only=manifest.review_mode == "teacher")
    answers = session_service.written_answers_for_export(body.session_id, body.session_secret, aid, tasks)
    if not answers:
        raise HTTPException(status_code=409, detail="No confirmed written answers are available for export")
    return build_export_response(aid, answers, manifest=manifest, pdf_bytes=pdf_bytes)


@app.get("/api/assignments/{assignment_id}/parse-diagnostics")
def parse_diagnostics(assignment_id: UUID, x_assignment_capability: str | None = Header(default=None)):
    """Return parse warnings and status for an assignment manifest."""
    try:
        _require_assignment_capability(str(assignment_id), x_assignment_capability)
        return get_parse_diagnostics(str(assignment_id))
    except HTTPException:
        raise
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("parse diagnostics failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not load parse diagnostics.")


@app.get("/api/teacher/assignments/{assignment_id}")
def teacher_assignment_review(assignment_id: UUID, x_assignment_capability: str | None = Header(default=None)):
    """Return the complete review manifest, including uncertain and rejected tasks."""
    try:
        _require_assignment_capability(str(assignment_id), x_assignment_capability)
        manifest = assignment_service.load_assignment_manifest_for_client(str(assignment_id))
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except assignment_service.AssignmentSourceMismatchError:
        raise HTTPException(status_code=409, detail="Worksheet source changed. Reload or re-upload it.")
    except ValueError:
        raise _assignment_not_found()
    if manifest.review_mode != "teacher":
        raise HTTPException(status_code=409, detail="Assignment is not in teacher review mode")
    return manifest.model_dump(mode="json")


@app.post("/api/teacher/assignments/{assignment_id}/review")
def update_teacher_assignment(
    assignment_id: UUID,
    body: TeacherReviewRequest,
    request: Request,
    x_assignment_capability: str | None = Header(default=None),
):
    """Apply explicit accept/edit/merge/split/hide/reject decisions and optionally finalize."""
    try:
        _require_assignment_capability(str(assignment_id), x_assignment_capability)
        _enforce_rate_limit(request, "assignment_mutation", config.MAX_MUTATIONS_PER_MINUTE, x_assignment_capability)
        manifest = review_assignment(
            str(assignment_id),
            [action.model_dump(exclude_unset=True) for action in body.actions],
            finalize=body.finalize,
        )
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return manifest.model_dump(mode="json")


@app.get("/api/assignments/{assignment_id}/pages/{page_number}.png")
def assignment_page_preview(
    assignment_id: UUID,
    page_number: int,
    request: Request,
    x_assignment_capability: str | None = Header(default=None),
):
    """Render an original worksheet page for the browser document canvas."""
    try:
        _require_assignment_capability(str(assignment_id), x_assignment_capability)
        _enforce_rate_limit(request, "page_render", config.MAX_PAGE_RENDERS_PER_MINUTE, x_assignment_capability)
        content = render_assignment_page(str(assignment_id), page_number)
    except HTTPException:
        raise
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except assignment_service.AssignmentSourceMismatchError:
        raise HTTPException(status_code=409, detail="Worksheet source changed. Reload or re-upload it.")
    except ValueError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception:
        logger.exception("page preview failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not render worksheet page.")
    return Response(content=content, media_type="image/png")


@app.delete("/api/assignments/{assignment_id}")
def delete_assignment_route(
    assignment_id: UUID,
    request: Request,
    x_assignment_capability: str | None = Header(default=None),
):
    """Delete assignment PDF, manifest, and related objects from storage."""
    _require_assignment_capability(str(assignment_id), x_assignment_capability)
    _enforce_rate_limit(request, "assignment_mutation", config.MAX_MUTATIONS_PER_MINUTE, x_assignment_capability)
    delete_assignment(str(assignment_id))
    return {"deleted": True, "assignment_id": str(assignment_id)}


@app.post("/upload")
async def upload_assignment(
    request: Request,
    file: UploadFile = File(...),
    review_mode: str = Query("direct", pattern="^(direct|teacher)$"),
):
    """Accept PDF, parse once, persist manifest + PDF, and return its safe canonical view."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    _enforce_rate_limit(request, "upload", config.MAX_UPLOADS_PER_MINUTE)
    assignment_id = str(uuid.uuid4())
    assignment_capability = assignment_service.create_assignment_capability()
    content = await _read_upload_bounded(file, config.MAX_UPLOAD_BYTES)
    if not config.looks_like_pdf(content):
        raise HTTPException(status_code=400, detail="Only valid PDF files are accepted.")
    try:
        if review_mode == "teacher":
            manifest = persist_assignment_from_pdf_bytes(
                assignment_id,
                content,
                review_mode=review_mode,
                assignment_capability_hash=assignment_service.assignment_capability_digest(assignment_capability),
            )
        else:
            manifest = persist_assignment_from_pdf_bytes(
                assignment_id,
                content,
                assignment_capability_hash=assignment_service.assignment_capability_digest(assignment_capability),
            )
        payload = manifest.to_questions_dict()
        record_metric("pdf_parse", status="ok" if manifest.parse_status == "ok" else "fallback")
        logger.info(
            "[POST /upload] Parsed questions: count=%s assignment_id=%s parse_status=%s",
            len(payload),
            assignment_id,
            manifest.parse_status,
        )
        return {
            "assignment_id": assignment_id,
            "assignment_capability": assignment_capability,
            "title": manifest.title,
            "document": manifest.to_client_document(),
            # Temporary compatibility projection for external clients. The
            # shipped browser consumes ``document`` as its source of truth.
            "questions": payload,
            "page_count": manifest.page_count,
            "parse_status": manifest.parse_status,
            "parse_warnings": manifest.parse_warnings,
            "parser": manifest.parser,
            "review_mode": manifest.review_mode,
            "review_status": manifest.review_status,
            "pages": (
                [page.model_dump(mode="json") for page in manifest.document.pages]
                if manifest.document is not None
                else []
            ),
        }
    except PDFProcessingError as exc:
        record_metric("pdf_parse", status="error", reason="malformed")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("PDF parse/upload failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not read that PDF. Please try another file.")


@app.get("/debug-gemini")
async def debug_gemini(request: Request):
    """Optional diagnostic: verify backend can reach Gemini text API. Disabled unless ENABLE_DEBUG_GEMINI is set."""
    if not config.is_debug_gemini_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    _enforce_rate_limit(request, "debug_provider", 1)
    try:
        return await debug_gemini_text_call()
    except Exception:
        logger.exception("[debug-gemini] FAILED")
        return {"status": "error", "error": "Gemini text call failed. Check server logs."}


@app.get("/api/samples")
async def list_official_samples():
    """Return the official canonical worksheet sample catalog."""
    from sample_catalog import list_product_samples

    return {
        "default_sample_id": "canonical-short-answer-ecosystems",
        "samples": [sample.to_public_dict() for sample in list_product_samples()],
    }


@app.get("/samples/{sample_id}.pdf")
async def serve_official_sample_pdf(sample_id: str):
    """Serve one official sample PDF for the normal upload flow."""
    from sample_catalog import get_product_sample

    try:
        sample = get_product_sample(sample_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sample worksheet not found") from None
    return FileResponse(sample.pdf_path, media_type="application/pdf")


@app.get("/samples/{sample_id}/preview.png")
async def serve_official_sample_preview(sample_id: str):
    """Serve a checked-in page preview for an official sample."""
    from sample_catalog import get_product_sample

    try:
        sample = get_product_sample(sample_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sample worksheet not found") from None
    if sample.preview_png_path is None or not sample.preview_png_path.exists():
        document = fitz.open(sample.pdf_path)
        try:
            pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
            return Response(content=pixmap.tobytes("png"), media_type="image/png")
        finally:
            document.close()
    return FileResponse(sample.preview_png_path, media_type="image/png")


@app.get("/sample-assignment.pdf")
async def serve_sample_assignment():
    """Backward-compatible alias for the default official sample PDF."""
    from sample_catalog import get_product_sample

    sample = get_product_sample(None)
    return FileResponse(sample.pdf_path, media_type="application/pdf")


@app.get("/test-assignment.pdf")
async def serve_test_assignment():
    """Legacy algebra fixture for explicit local diagnostics only."""
    if not config.is_debug_routes_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    path = config.ROOT / "test_assignment.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="application/pdf")


@app.get("/sample-page.png")
async def serve_sample_page_preview():
    """Render the first page of the default official sample for landing previews."""
    return await serve_official_sample_preview("canonical-short-answer-ecosystems")


@app.get("/sample-workspace.png")
async def serve_sample_workspace_preview():
    """Serve the checked-in sample workspace image used on the landing page."""
    path = config.ROOT / "frontend" / "sample-workspace.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="sample-workspace.png not found")
    return FileResponse(path, media_type="image/png")


@app.get("/genai.bundle.js", response_class=Response)
async def serve_genai_bundle():
    """Serve the bundled @google/genai SDK for browser (no runtime CDN)."""
    path = config.ROOT / "frontend" / "genai.bundle.js"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Gemini SDK bundle missing. Run: npm install && npm run build:genai, then commit frontend/genai.bundle.js",
        )
    return FileResponse(path, media_type="application/javascript; charset=utf-8")


@app.get("/session-rules.js", response_class=Response)
async def serve_session_rules():
    """Serve session intent helpers used by the worksheet UI (see tests/session-rules.test.cjs)."""
    path = config.ROOT / "frontend" / "session-rules.js"
    if not path.exists():
        raise HTTPException(status_code=503, detail="session-rules.js missing from frontend/")
    return FileResponse(path, media_type="application/javascript; charset=utf-8")


@app.get("/question-view.js", response_class=Response)
async def serve_question_view_js():
    """Serve the isolated worksheet question-card renderer."""
    path = config.ROOT / "frontend" / "question-view.js"
    if not path.exists():
        raise HTTPException(status_code=503, detail="question-view.js missing from frontend/")
    return FileResponse(path, media_type="application/javascript; charset=utf-8")


@app.get("/worksheet-view.js", response_class=Response)
async def serve_worksheet_view_js():
    path = config.ROOT / "frontend" / "worksheet-view.js"
    if not path.exists():
        raise HTTPException(status_code=503, detail="worksheet-view.js missing from frontend/")
    return FileResponse(path, media_type="application/javascript; charset=utf-8")


@app.get("/ui-state.js", response_class=Response)
async def serve_ui_state_js():
    path = config.ROOT / "frontend" / "ui-state.js"
    if not path.exists():
        raise HTTPException(status_code=503, detail="ui-state.js missing from frontend/")
    return FileResponse(path, media_type="application/javascript; charset=utf-8")


@app.get("/app.js", response_class=Response)
async def serve_app_js():
    """Serve the worksheet app client script."""
    path = config.ROOT / "frontend" / "app.js"
    if not path.exists():
        raise HTTPException(status_code=503, detail="app.js missing from frontend/")
    return FileResponse(path, media_type="application/javascript; charset=utf-8")


@app.get("/favicon.png")
async def serve_favicon():
    """Serve the Claros favicon asset."""
    path = config.ROOT / "claros favicon.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="claros favicon.png not found")
    return FileResponse(path, media_type="image/png")


@app.get("/logo.png")
async def serve_logo():
    """Serve the Claros navbar logo asset."""
    path = config.ROOT / "claros logo.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="claros logo.png not found")
    return FileResponse(path, media_type="image/png")


@app.get("/styles/{filename}")
async def serve_style(filename: str):
    """Serve frontend CSS assets (tokens, landing, app)."""
    if not filename.endswith(".css") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Not found")
    path = config.ROOT / "frontend" / "styles" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="text/css; charset=utf-8")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the Claros landing page (frontend/landing.html) only."""
    path = config.ROOT / "frontend" / "landing.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="landing.html not found")
    return FileResponse(path, media_type="text/html")


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    """Serve the Claros worksheet app (frontend/app.html)."""
    path = config.ROOT / "frontend" / "app.html"
    if not path.exists():
        return HTMLResponse("<h1>Not found</h1><p>app.html missing</p>", status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/test", response_class=HTMLResponse)
async def test_voice_page():
    """Serve the voice debug test page."""
    if not config.is_debug_routes_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    path = config.ROOT / "test_voice.html"
    if not path.exists():
        return HTMLResponse("<h1>Not found</h1><p>test_voice.html missing</p>", status_code=404)
    return FileResponse(path, media_type="text/html")
