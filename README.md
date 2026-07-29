# Claros

> **Present tense:** Claros is a human-free worksheet-understanding and tutoring
> system for structured PDF worksheets. Revamp Stages 1–12 are on `main`
> (records in [`docs/BUILD_WEEK_DELTA.md`](docs/BUILD_WEEK_DELTA.md)); Stages
> 13–14 finish documentation convergence and whole-product audit. Historical
> Build Week / OpenAI / parser-experiment plans are **not** the current product —
> see banners on those docs. Canonical technical boundary:
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**An AI agent primarily for students with typing difficulties — it understands structured worksheet PDFs, guides reasoning through voice or typing, and writes the student-confirmed answer into a safe response region (or the labeled side panel) only after the student has stated or approved that exact answer.**

## Demo

[**Watch the demo**](https://www.youtube.com/watch?v=lBat2W_Ycsk)

## The Problem

Students working through structured assignments typically juggle a worksheet, a help tool, and manual text entry. Each context switch slows them down and breaks their reasoning flow.

For students with typing difficulties - whether due to motor impairments, dyslexia, injury, or other conditions - the manual entry step is a significant barrier. The cognitive work of arriving at an answer is separate from the physical work of typing it, yet most tools treat them as the same step.

Existing AI tutors either give away answers immediately (undermining learning) or require typed input (excluding users who struggle with typing). There is a gap for a tool that preserves guided reasoning while removing the typing bottleneck for the final answer entry step.

Claros closes this gap. It operates directly on the worksheet: guiding the student through each task via voice or typed interaction, then writing only the student-confirmed answer when placement is safe.

## How Claros Works

1. **Upload a worksheet PDF or open an official sample** — Claros builds deterministic physical evidence, keeps page geometry, and projects tasks and response regions onto the original worksheet pages.
2. **Use voice and/or typing** — Voice (Gemini Live) is optional. Typed interaction always works; microphone access is never required.
3. **Discuss a task** — Claros guides the student through the problem using Socratic questioning. Guided reasoning first, not answer generation.
4. **State and confirm the exact final answer** — The student states or edits their answer, then explicitly confirms that exact text for that task.
5. **Write only after confirmation** — Confirmation and writing are distinct. After confirm, deterministic code stamps the exact confirmed text into a validated region (or the labeled side panel when placement is unsafe).
6. **Export as PDF** — Export writes confirmed answers onto the **original worksheet PDF** at approved regions; uncertain or overflow content goes to appended side-panel pages.

## Core Product Rule

Claros enforces a deliberate constraint: **confirm ≠ write.** It will not write an answer until the student has explicitly confirmed the exact proposed answer for that specific task.

- If the student asks Claros to write before they have given and confirmed their answer, Claros will not stamp the worksheet.
- This rule is enforced per task. Confirming an answer for task 1 does not unlock writing for task 2.
- The frontend may propose readiness from conversation cues, but the write API only stamps the exact confirmed candidate after a server-issued, single-use write token. The backend does **not** regenerate the answer from conversation history.

This is an intentional product decision. Claros is designed to support learning, not to bypass it. Voice removes the typing barrier when available; typed fallback preserves full access; the confirmation gate preserves the reasoning requirement.

## Why This Matters

Many students can reason through a problem but struggle to record their answer in a structured format. Claros lets them do the hard part - thinking - with their voice, and handles the mechanical part - typing the answer into the right box - for them.

This is not about making assignments easier. It is about making them accessible to students who already know the material but are blocked by the input method.

## Features

- **PDF assignment ingestion** - Upload a PDF worksheet. Claros detects numbered questions, page geometry, and proposed answer regions for overlay editing.
- **Layout-preserving worksheet view** - Original page previews are shown with accessible answer fields positioned on the page. Unsafe or low-confidence placement routes confirmed answers to a labeled side panel instead of guessing coordinates; the student app does not offer free-form region editing.
- **PDF safety limits** - Uploads are bounded by byte size, page count, and extracted-text size; malformed or unsupported PDFs return a recoverable validation error.
- **OCR-required detection and candidate adapter** - Image-only/scanned pages are marked `requires_ocr` without fake questions. PP-StructureV3 is available only through an optional, feature-flagged adapter pending corpus and Cloud Run promotion evidence.
- **Real-time voice conversation** - Bidirectional audio through Gemini Live. The student speaks and hears Claros respond with natural voice.
- **Socratic guidance** - Claros defaults to teaching mode, asking guiding questions rather than stating answers.
- **Per-question answer readiness tracking** - The frontend tracks whether the student has stated a final answer for each question before allowing a write.
- **Controlled answer writing** - After explicit student confirmation, the frontend calls the backend write API with an answer-bound, single-use token. The backend stamps that exact confirmed text; no model rewrites it, including LaTeX-style `$...$` delimiters.
- **Live transcript** - Both sides of the conversation are transcribed and displayed in real time (from Gemini Live in the browser).
- **PDF export onto the original worksheet** - Export inserts answers only into approved regions on the original PDF. Confirmed answers without safe coordinates are preserved on appended side-panel pages instead of being silently skipped, truncated, or written to a guessed location. Export requires at least one confirmed written answer.
- **Answer-stated indicator** - The UI shows a visual badge when the student (or Claros) has indicated the answer for a given question.
- **Barge-in / interruption** - If the student starts speaking while Claros is talking, Claros’ audio playback is stopped and the app returns to listening. An **Interrupt** button (visible during a session) stops Claros's speech immediately so the student can talk without speaking first.
- **Voice-enabled PDF export** - Saying phrases like “export pdf” or “export this as pdf” from within the voice session triggers the same PDF export as the button, including the same “at least one written answer” requirement.

## Architecture

```mermaid
flowchart LR
  Browser[Browser] --> Landing[GET / → landing.html]
  Browser --> App[GET /app → app.html]
  App --> Upload[POST /upload]
  Upload --> Parser[Hybrid physical IR (default) / legacy or paddle flags]
  Parser --> Semantics[Gemini structured semantic classification]
  Parser --> Storage[(Google Cloud Storage)]
  App --> Session[Session start / restore / confirm]
  Session --> Storage
  App --> Live[Direct Gemini Live]
  App --> Write[POST /api/write]
  Write --> Stamp[Deterministic confirmed-text stamp]
  App --> Export[POST /export]
  Export --> PDF[Original PDF + regions]
```

```
Browser (frontend/landing.html at `/`, frontend/app.html at `/app`)
  │
  ├── Shared styles: frontend/styles/tokens.css + landing.css | app.css
  ├── Worksheet client: frontend/app.js + worksheet-view.js + session-rules.js
  ├── GET /api/session-config/{id}  → ephemeral token + system prompt + model
  ├── GET /api/assignments/{id}/pages/{n}/preview → original page PNG
  ├── Direct WebSocket to Gemini Live API (voice: audio in/out, transcription)
  │     via bundled @google/genai JS SDK (served from app; no runtime CDN), ephemeral token from backend
  └── POST /api/write/{id} (streaming) → answer text for a question

FastAPI backend (main.py + service modules)
  │
  ├── config.py — env, GCS bucket, API key helpers
  ├── assignment_service.py — load/parse assignments from GCS, page preview, export assembly
  ├── gemini_service.py — ephemeral tokens and confirmed-text stamping
  ├── storage.py — GCS upload
  ├── schemas.py — request validation
  ├── Ephemeral token creation (auth_tokens.create) for browser-Gemini Live
  ├── Gemini structured page/block/task classification
  ├── PDF parser (parser.py + parser_layout.py - PyMuPDF geometry; default PDF_PARSER_MODE=hybrid)
  ├── Hybrid document model + optional PP-StructureV3 adapter (ENABLE_PADDLEOCR flagged; not required)
  ├── Gemini structured page/block/task classification
  ├── PDF exporter (exporter.py - layout-preserving primary, ReportLab legacy fallback)
  └── Google Cloud Storage (assignment PDF persistence)
```

**Real-time voice** uses **Gemini Live directly from the browser**. The backend does not proxy audio. On "Start Session", the frontend loads the Gemini SDK from the app’s own asset (`/genai.bundle.js`, built from `@google/genai` and checked in), fetches an ephemeral token and session config from `GET /api/session-config/{assignment_id}`, then connects to Gemini Live. The browser captures mic at 16 kHz PCM, sends audio to Gemini, and plays back responses. Transcripts are handled in the client; write detection (e.g. "write my answer for question N") and answer-stated detection run in the frontend.

**Answer writing** is available only after the student confirms the exact answer for that task. The frontend calls `POST /api/write/{assignment_id}` with the confirmed candidate and a single-use token; the backend validates the task snapshot and streams that exact text into the correct question field. The write route does not call a text model or accept conversation as write authority.

**Barge-in / interruption** is implemented in the frontend. When the user starts speaking (or clicks the **Interrupt** button) while Claros is playing, the browser stops scheduled audio buffers, clears the playback queue, and returns to listening. This is not full-duplex.

**Voice-enabled PDF export** is detected on the user speech path in the browser. When a user utterance for a completed turn clearly matches export-intent phrases (e.g., “export pdf”, “export as pdf”, “export this as pdf”, “download pdf”, “download the pdf”, “save as pdf”, “save this as pdf”, “save it as pdf”), the frontend triggers the same `/export/{assignment_id}` route as the Export button. Export still requires at least one confirmed written answer; answered text is placed onto the original worksheet when regions are available.

**Answer confirmation** is required before any worksheet stamp: the student must confirm the exact candidate for that task. Models may propose tutoring actions from supplied evidence; deterministic code owns write tokens, geometry validation, authorization, overflow, and PDF changes.

**PDF pipeline**: Uploaded PDFs are stored in Google Cloud Storage under `assignments/{uuid}/assignment.pdf`, parsed into the versioned canonical document contract (see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and `LAYOUT.md`), previewed as page images, and exported by writing answers into the original PDF regions when safe.

Current runtime architecture is [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Parser mode defaults to **`PDF_PARSER_MODE=hybrid`**. July 2026 PDF-understanding investigation notes (legacy-default experiments, optional teacher-review sketches) are historical: [`docs/pdf-understanding-architecture.md`](docs/pdf-understanding-architecture.md).

## Hardening and risk prevention

The backend and frontend include guardrails to reduce common failure modes:

- **Upload abuse**: chunked reads with max byte limit (`MAX_UPLOAD_BYTES`, default 10 MiB) plus tolerant `%PDF-` signature validation (leading whitespace/BOM allowed).
- **API correctness**: dependency failures return 5xx; 404 is reserved for genuinely missing assignments.
- **Input contracts**: write payloads use strict conversation schema (speaker enum, bounded text); long histories are trimmed to the most recent `CONVERSATION_TRIM_TURNS` (default 200) instead of failing mid-session. Hard cap: `MAX_CONVERSATION_TURNS` (default 400).
- **Storage determinism**: uploads always use canonical `assignment.pdf`; legacy multi-blob prefixes fall back to sorted `.pdf` selection.
- **Privacy-aware logging**: operational logs avoid assignment titles and question text.
- **Accessibility/resilience**: worksheet upload has an explicit keyboard button; session live badge has class-based fallback beyond CSS `:has()`.
- **Voice fallback**: microphone denial, unavailable audio, and provider connection failures leave typed answers, confirmation, and export available.
- **Session-secret protection**: new durable session records store a keyed hash instead of the client secret in plaintext; verification remains constant-time.
- **Privacy-safe observability**: operational metrics use fixed event names and bounded status/reason labels; document, question, answer, token, and secret content is excluded.
- **CI consistency**: parallel CI jobs (python coverage+lint, frontend contract+bundle, docker smoke); deploy gated by verify job + post-deploy probes.

When extending Claros, preserve these invariants: validate at API boundaries, keep error semantics explicit, and add regression tests for each new guardrail.

## Google Cloud Deployment

Claros is deployed on **Google Cloud Run** as a containerized service.

- **Container image** is built from the project `Dockerfile` (Python 3.11, FastAPI/Uvicorn).
- **Assignment PDFs** are stored in a **Google Cloud Storage** bucket. The upload, session-config, write, and export endpoints use GCS where needed.
- **Gemini API**: The backend holds the Gemini API key for (1) ephemeral browser-Gemini Live tokens and (2) closed-world document semantics. The browser never receives the API key; it uses a short-lived token for Live only.
- Cloud Run provides automatic HTTPS, scaling, and a public URL for the frontend.

**Deploying:**

1. **Ensure the Gemini SDK bundle exists** (no runtime CDN). From project root, run once (requires Node 18+):

   ```bash
   npm install && npm run build:genai
   ```

   This writes `frontend/genai.bundle.js`. Commit it so the Docker image includes it. If the bundle is missing, the app will return 503 when the frontend requests it.

2. **Build and push the container** (from project root):

```bash
gcloud builds submit --tag gcr.io/<PROJECT_ID>/claros

# Deploy to Cloud Run
gcloud run deploy claros \
  --image gcr.io/<PROJECT_ID>/claros \
  --platform managed \
  --region <REGION> \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=<key>,GCS_BUCKET_NAME=<bucket>,GOOGLE_CLOUD_PROJECT=<project>
```

Replace `<PROJECT_ID>`, `<REGION>`, `<key>`, `<bucket>`, and `<project>` with your values.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Voice AI | Gemini Live API (direct from browser via bundled @google/genai; SDK served from app; ephemeral token from backend) |
| Text AI | Gemini structured document semantics; confirmed writes are deterministic |
| PDF parsing | PyMuPDF (fitz) |
| PDF export | Original PDF via PyMuPDF (ReportLab legacy fallback only) |
| Storage | Google Cloud Storage |
| Frontend | HTML, CSS, vanilla JavaScript |
| Deployment | Docker, Google Cloud Run |

## Local Setup

**Prerequisites:**
- Python 3.11+
- Node.js 18+ and npm (only if you need to rebuild `frontend/genai.bundle.js`; see **Gemini SDK bundle** below)
- A Google Cloud project with Cloud Storage enabled
- A Gemini API key
- A GCS bucket for storing uploaded assignments

**Steps:**

```bash
# Clone the repository
git clone https://github.com/ChimdumebiNebolisa/Claros.git
cd Claros

# Install dependencies
pip install -r requirements-server.txt

# Create .env file
cp .env.example .env  # or create manually (see Environment Variables below)

# Generate a test PDF (optional)
python test_assignment.py

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser. Upload a PDF, or from `/app` choose
one of the official samples (Short Answer, Multiple Choice, or Math Practice).
Samples use the same upload and session path as a student worksheet.

**Gemini SDK bundle:** The frontend loads the Gemini SDK from `/genai.bundle.js` (same origin). That file is produced by `npm run build:genai` and checked in under `frontend/genai.bundle.js`. There is no runtime dependency on esm.sh or any other CDN.

**Note:** Microphone access is requested only if the student starts a voice session. Typed confirmation, writing, and export remain fully usable without a mic. Use Chrome or a Chromium-based browser for best WebSocket and audio API support.

## Environment Variables

Create a `.env` file in the project root:

```
GEMINI_API_KEY=<your-gemini-api-key>
GCS_BUCKET_NAME=<your-gcs-bucket-name>
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GEMINI_TEXT_MODEL=gemini-2.5-flash
# DOCUMENT_SEMANTIC_PROVIDER=gemini
# PDF_PARSER_MODE=hybrid
# ENABLE_PADDLEOCR=false
# ALLOW_SYNCHRONOUS_PADDLEOCR=false
# ENABLE_DOCUMENT_SEMANTICS=true
# ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS=true
# ENABLE_DOCUMENT_TASK_AUTO_APPROVE=false
```

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | API key for Gemini voice and closed-world document semantics; required in production |
| `GCS_BUCKET_NAME` | Google Cloud Storage bucket name for storing uploaded PDFs |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID |
| `GEMINI_TEXT_MODEL` | Gemini model used for closed-world document semantics (default: `gemini-2.5-flash`) |
| `ENABLE_DEBUG_GEMINI` | Set to `true` to expose `GET /debug-gemini` for local Gemini connectivity checks (default: disabled) |
| `ENABLE_DEBUG_ROUTES` | Set to `true` only for local legacy diagnostic routes such as `GET /test` (default: disabled) |
| `DOCUMENT_SEMANTIC_PROVIDER` | `gemini` (default) or `none` for document semantics |
| `APP_ENV` | Canonical environment name (`development` or `production`); if legacy `CLAROS_ENV` is also set, both values must match |
| `MAX_SESSION_STARTS_PER_MINUTE` | Maximum durable session creations per caller in the sliding window (production default: 30) |
| `PDF_PARSER_MODE` | `hybrid` (default), `legacy`, or `paddle`; hybrid builds deterministic physical evidence before Gemini selection |
| `ENABLE_PADDLEOCR` | Enable the local PP-StructureV3 adapter (default: false) |
| `ALLOW_SYNCHRONOUS_PADDLEOCR` | Development-only worker escape hatch; keep false on the upload service (default: false) |
| `ENABLE_DOCUMENT_SEMANTICS` | Enable strict closed-world document classification (default: true) |
| `ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS` | Run the configured compiler during upload (default: true) |
| `ENABLE_DOCUMENT_TASK_AUTO_APPROVE` | Allow high-confidence hybrid tasks to bypass review; keep false until benchmark promotion (default: false) |
| `PADDLEOCR_DPI` | Page render DPI for the candidate adapter (default: 150) |
| `PADDLEOCR_CPU_THREADS` | CPU inference thread count (default: 4) |

Local development may also require Google Cloud application credentials for GCS access (e.g., `GOOGLE_APPLICATION_CREDENTIALS` or `gcloud auth application-default login`).

## Development

Install dev dependencies and run the full local check suite:

```bash
pip install -r requirements-dev.txt
npm ci

# Python: lint + tests with coverage gate (72% minimum on app modules)
python -m ruff check agent.py assignment_service.py config.py exporter.py gemini_service.py main.py parser.py schemas.py storage.py tests/
pytest tests/ --cov --cov-config=pyproject.toml --cov-report=term-missing

# Frontend: session rules table + static HTML/JS contract checks + genai bundle build
npm run ci:frontend

# Optional: build the production container locally
docker build -t claros:local .
```

**Test layers**

| Layer | What it covers | Command |
|-------|----------------|---------|
| Parser / export | PDF extraction, Unicode normalization, ReportLab export | `pytest tests/test_parser.py tests/test_exporter.py tests/test_unicode_text.py` |
| API integration | Static routes, upload validation, write/export/session-config | `pytest tests/test_main_integration.py tests/test_upload_validation.py tests/test_session_config.py` |
| Service units | GCS paths, schema trim/validation, assignment export helpers | `pytest tests/test_storage.py tests/test_schemas.py tests/test_assignment_service.py` |
| Frontend contract | Required ids/links in `landing.html`, `app.html`, `app.js` | `npm run validate:frontend` |
| Session rules | Voice intent phrase table (15 cases) | `npm run test:session-rules` |
| Docker smoke | Image builds and serves `/` on port 8080 | CI `docker` job |

**CI/CD (GitHub Actions)**

- **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)** — runs on every push/PR (parallel jobs):
  - `python`: Ruff lint, pytest with coverage gate + XML artifact, metrics script
  - `frontend`: `npm run ci:frontend` (session rules, contract validation, genai bundle) + artifact upload
  - `docker`: production image build + container boot smoke test (`curl /`)
- **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)** — runs on `main` push:
  - `verify`: repeats lint, pytest+coverage, frontend CI, and docker build before deploy
  - `deploy`: builds genai bundle, pushes image to GCR, deploys Cloud Run, post-deploy smoke (`/`, `/app`, `/styles/tokens.css`)

If branch protection blocks merges, set the required check to the **`CI`** workflow (not the removed `Tests` workflow).

The optional `requirements-voice.txt` stack is for `test_voice.py` (standalone mic/speaker voice test); the main app uses `requirements-server.txt` only.

## Current Limitations

- **Worksheet-focused scope** - Claros works with structured assignments that follow a "Question N:" format. It is not a general-purpose document editor.
- **Heuristic answer detection** - Answer readiness is determined in the frontend by matching common phrasing patterns (e.g., "my answer is…", "I think it's…"). Unusual phrasings may not be detected.
- **Single-session state** - Conversation and answer readiness are held in memory in the browser. Refreshing the page starts a new session.
- **PDF format dependency** - Question extraction relies on "Question N:" line patterns. PDFs with different formatting may fall back to single-block extraction.
- **Voice model compliance** - The system prompt guides tutoring behavior, but LLM compliance is not assumed. The backend enforces student confirmation, task binding, single-use write authorization, and exact confirmed-text stamping independently of the conversation.
- **Direct Gemini Live** - Voice runs browser → Gemini Live. The frontend loads the `@google/genai` SDK from the app’s own asset (`/genai.bundle.js`); no runtime CDN. The bundle must be built once with `npm run build:genai` and committed.
- **Ephemeral tokens** - Session config uses the Gemini API to create short-lived tokens. If token creation fails (e.g. API or region limitation), the backend returns 500 and the user must retry or check logs.
- **Basic barge-in** - When the user starts speaking (or clicks Interrupt) while Claros is talking, frontend playback is stopped and the app returns to listening. This is not full-duplex.
- **Heuristic voice export intent** - Voice-triggered export uses phrase matching (e.g., “export pdf”, “export as pdf”, “download pdf”, “save as pdf”). Transcript quality in noisy environments may affect detection.
- **Browser audio processing** - The browser is asked (via getUserMedia constraints) to enable echo cancellation, noise suppression, automatic gain control, and mono capture. Actual behavior depends on the user’s device and browser support.
- **Browser compatibility** - Requires a modern browser with WebSocket, AudioContext, and getUserMedia. Tested primarily on Chrome.

## Future Improvements

- Richer answer detection using a lightweight classifier instead of regex heuristics
- Session persistence so students can resume interrupted sessions
- Multi-format PDF support beyond "Question N:" patterns
- Accessibility audit with assistive technology users
- Full-duplex interruption handling for smoother barge-in
