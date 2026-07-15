"""
Claros backend: FastAPI app with PDF upload, session config (ephemeral token), and write/export.
Real-time voice uses Gemini Live directly from the browser.
"""
import json
import logging
import uuid
from uuid import UUID

import fitz
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

import assignment_service
from assignment_service import (
    build_export_response,
    delete_assignment,
    get_parse_diagnostics,
    persist_assignment_from_pdf_bytes,
    render_assignment_page,
)
import config
from gemini_service import create_session_config, debug_gemini_text_call, stamp_confirmed_answer, stream_write_answer
from schemas import (
    ExportRequest,
    SessionConfirmRequest,
    SessionRestoreRequest,
    SessionStartRequest,
    WriteRequest,
    trim_conversation,
    validate_export_answers,
)
import session_service
import storage
from observability import record_metric
from parser import PDFProcessingError

logger = logging.getLogger(__name__)

app = FastAPI()


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
def get_session_config(assignment_id: UUID):
    """Return ephemeral token + system prompt + model for browser-side Gemini Live. API key stays on server."""
    aid = str(assignment_id)
    try:
        return create_session_config(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
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
def start_tutoring_session(body: SessionStartRequest):
    """Create a durable server-side session for an assignment."""
    aid = body.assignment_id.strip()
    try:
        _ = UUID(aid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assignment_id")
    try:
        title, questions = assignment_service.load_assignment_from_gcs(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("session start load failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Could not load assignment. Please try again.")
    qids = [q["id"] for q in questions]
    payload = session_service.create_session(aid, qids)
    record_metric("session_created", status="ok")
    payload["title"] = title
    payload["questions"] = questions
    return payload


@app.post("/api/session/{session_id}/confirm")
def confirm_answer_for_question(session_id: UUID, body: SessionConfirmRequest):
    """Explicitly confirm a student-owned answer and receive a single-use write token."""
    result = session_service.confirm_answer(
        str(session_id),
        body.session_secret,
        body.question_id,
        body.answer_text,
    )
    record_metric("confirmation", status="ok")
    return result


@app.post("/api/session/{session_id}/restore")
def restore_session(session_id: UUID, body: SessionRestoreRequest):
    """Restore confirmed-answer state after a browser refresh."""
    return session_service.restore_session_for_client(str(session_id), body.session_secret)


@app.post("/api/write/{assignment_id}")
async def stream_write(assignment_id: UUID, body: WriteRequest):
    """Stream generated answer text for a question. Frontend calls this when write is triggered."""
    aid = str(assignment_id)
    if config.ENFORCE_WRITE_CONTRACT:
        if not body.answer_candidate.strip():
            raise HTTPException(status_code=400, detail="answer_candidate must be non-empty")
        if not body.write_token or not body.session_id or not body.session_secret:
            raise HTTPException(status_code=403, detail="Confirmed write_token and session credentials are required")
        state = session_service.load_session(body.session_id)
        if state.assignment_id != aid:
            raise HTTPException(status_code=403, detail="Session does not match assignment")
        if not state.verify_session_secret(body.session_secret):
            raise HTTPException(status_code=403, detail="Invalid session credentials")
        session_service.validate_write_token(state, body.question_id, body.answer_candidate, body.write_token)
    try:
        title, questions = assignment_service.load_assignment_from_gcs(aid)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("write load failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Could not load assignment. Please try again.")
    qids = [q["id"] for q in questions]
    if body.question_id not in qids:
        raise HTTPException(status_code=400, detail=f"Unknown question id: {body.question_id}")
    trimmed = trim_conversation(body.conversation)
    if len(trimmed) < len(body.conversation):
        logger.info(
            "Trimmed write conversation from %s to %s turns for assignment %s",
            len(body.conversation),
            len(trimmed),
            aid,
        )
    # Confirmed writes already passed the single-use token/fingerprint gate.
    # Stamp the approved text instead of waiting on Gemini reformatting.
    if config.ENFORCE_WRITE_CONTRACT:
        return StreamingResponse(
            stamp_confirmed_answer(body.answer_candidate or ""),
            media_type="text/plain; charset=utf-8",
        )
    return StreamingResponse(
        stream_write_answer(
            aid,
            body.question_id,
            [item.model_dump() for item in trimmed],
            body.answer_candidate or "",
        ),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/export/{assignment_id}")
async def export_assignment_get(assignment_id: UUID, answers: str = Query(..., alias="answers")):
    """Generate PDF of questions and answers. Query param 'answers' = JSON array of {question_id, answer_text}."""
    aid = str(assignment_id)
    try:
        answers_list = json.loads(answers)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid answers JSON")
    return build_export_response(aid, validate_export_answers(answers_list))


@app.post("/export/{assignment_id}")
async def export_assignment_post(assignment_id: UUID, body: ExportRequest):
    """Generate PDF of questions and answers from a JSON body."""
    return build_export_response(str(assignment_id), validate_export_answers(body.answers))


@app.get("/api/assignments/{assignment_id}/parse-diagnostics")
def parse_diagnostics(assignment_id: UUID):
    """Return parse warnings and status for an assignment manifest."""
    try:
        return get_parse_diagnostics(str(assignment_id))
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("parse diagnostics failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not load parse diagnostics.")


@app.get("/api/assignments/{assignment_id}/pages/{page_number}.png")
def assignment_page_preview(assignment_id: UUID, page_number: int):
    """Render an original worksheet page for the browser document canvas."""
    try:
        content = render_assignment_page(str(assignment_id), page_number)
    except assignment_service.AssignmentExpiredError:
        raise HTTPException(status_code=410, detail="Assignment expired")
    except ValueError:
        raise HTTPException(status_code=404, detail="Page not found")
    except Exception:
        logger.exception("page preview failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not render worksheet page.")
    return Response(content=content, media_type="image/png")


@app.delete("/api/assignments/{assignment_id}")
def delete_assignment_route(assignment_id: UUID):
    """Delete assignment PDF, manifest, and related objects from storage."""
    delete_assignment(str(assignment_id))
    return {"deleted": True, "assignment_id": str(assignment_id)}


@app.post("/upload")
async def upload_assignment(file: UploadFile = File(...)):
    """Accept PDF, parse once, persist manifest + PDF. Returns assignment_id, title, questions."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    assignment_id = str(uuid.uuid4())
    content = await _read_upload_bounded(file, config.MAX_UPLOAD_BYTES)
    if not config.looks_like_pdf(content):
        raise HTTPException(status_code=400, detail="Only valid PDF files are accepted.")
    try:
        manifest = persist_assignment_from_pdf_bytes(assignment_id, content)
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
            "title": manifest.title,
            "questions": payload,
            "page_count": manifest.page_count,
            "parse_status": manifest.parse_status,
            "parse_warnings": manifest.parse_warnings,
        }
    except PDFProcessingError as exc:
        record_metric("pdf_parse", status="error", reason="malformed")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("PDF parse/upload failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not read that PDF. Please try another file.")


@app.get("/debug-gemini")
async def debug_gemini():
    """Optional diagnostic: verify backend can reach Gemini text API. Disabled unless ENABLE_DEBUG_GEMINI is set."""
    if not config.is_debug_gemini_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return await debug_gemini_text_call()
    except Exception:
        logger.exception("[debug-gemini] FAILED")
        return {"status": "error", "error": "Gemini text call failed. Check server logs."}


@app.get("/test-assignment.pdf")
async def serve_test_assignment():
    """Serve the test assignment PDF from the project root."""
    path = config.ROOT / "test_assignment.pdf"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="test_assignment.pdf not found. Run test_assignment.py to generate it.",
        )
    return FileResponse(path, media_type="application/pdf")


@app.get("/sample-page.png")
async def serve_sample_page_preview():
    """Render the first page of the shipped sample for the real landing preview."""
    path = config.ROOT / "test_assignment.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample worksheet not found")
    document = fitz.open(path)
    try:
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        return Response(content=pixmap.tobytes("png"), media_type="image/png")
    finally:
        document.close()


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
    path = config.ROOT / "test_voice.html"
    if not path.exists():
        return HTMLResponse("<h1>Not found</h1><p>test_voice.html missing</p>", status_code=404)
    return FileResponse(path, media_type="text/html")
