"""
Claros backend: FastAPI app with PDF upload, session config (ephemeral token), and write/export.
Real-time voice uses Gemini Live directly from the browser.
"""
import json
import logging
import os
import tempfile
import uuid
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse

import assignment_service
import storage
from assignment_service import build_export_response
import config
from gemini_service import create_session_config, debug_gemini_text_call, stream_write_answer
from parser import parse_pdf
from schemas import ExportRequest, WriteRequest, validate_export_answers

logger = logging.getLogger(__name__)

app = FastAPI()


def _assignment_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Assignment not found")


@app.get("/api/session-config/{assignment_id}")
def get_session_config(assignment_id: UUID):
    """Return ephemeral token + system prompt + model for browser-side Gemini Live. API key stays on server."""
    aid = str(assignment_id)
    try:
        return create_session_config(aid)
    except ValueError:
        raise _assignment_not_found()
    except RuntimeError as e:
        if "token" in str(e).lower():
            raise HTTPException(status_code=500, detail="Session setup failed. Please try again.")
        raise HTTPException(status_code=500, detail="Session setup failed. Please try again.")
    except Exception:
        logger.exception("session-config failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Session setup failed. Please try again.")


@app.post("/api/write/{assignment_id}")
async def stream_write(assignment_id: UUID, body: WriteRequest):
    """Stream generated answer text for a question. Frontend calls this when write is triggered."""
    aid = str(assignment_id)
    try:
        title, questions = assignment_service.load_assignment_from_gcs(aid)
    except ValueError:
        raise _assignment_not_found()
    except Exception:
        logger.exception("write load failed for assignment %s", aid)
        raise HTTPException(status_code=500, detail="Could not load assignment. Please try again.")
    qids = [q["id"] for q in questions]
    if body.question_id not in qids:
        raise HTTPException(status_code=400, detail=f"Unknown question id: {body.question_id}")
    return StreamingResponse(
        stream_write_answer(
            aid,
            body.question_id,
            [item.model_dump() for item in body.conversation],
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


@app.post("/upload")
async def upload_assignment(file: UploadFile = File(...)):
    """Accept PDF, upload to GCS, parse questions. Returns assignment_id, title, questions."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    assignment_id = str(uuid.uuid4())
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size.")
    if not content.startswith(config.PDF_MAGIC):
        raise HTTPException(status_code=400, detail="Only valid PDF files are accepted.")
    try:
        storage.upload_pdf_to_gcs(assignment_id, content, file.filename or "assignment.pdf")
    except Exception:
        logger.exception("GCS upload failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Upload failed. Please try again.")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        title, questions = parse_pdf(tmp_path)
        payload = [{"id": q.id, "text": q.text} for q in questions]
        logger.info(
            "[POST /upload] Parsed questions: title=%r count=%s",
            title,
            len(payload),
        )
        return {
            "assignment_id": assignment_id,
            "title": title,
            "questions": payload,
        }
    except Exception:
        logger.exception("PDF parse failed for assignment %s", assignment_id)
        raise HTTPException(status_code=500, detail="Could not read that PDF. Please try another file.")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


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
