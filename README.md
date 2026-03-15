# Claros

**An AI agent primarily for students with typing difficulties — it reads assignments, guides reasoning through real-time voice conversation, and writes the final answer into the correct question field only after the student has worked it out or stated it.**

![Claros interface screenshot](images/image.png)

## The Problem

Students working through structured assignments typically juggle a worksheet, a help tool, and manual text entry. Each context switch slows them down and breaks their reasoning flow.

For students with typing difficulties — whether due to motor impairments, dyslexia, injury, or other conditions — the manual entry step is a significant barrier. The cognitive work of arriving at an answer is separate from the physical work of typing it, yet most tools treat them as the same step.

Existing AI tutors either give away answers immediately (undermining learning) or require typed input (excluding users who struggle with typing). There is a gap for a tool that preserves guided reasoning while removing the typing bottleneck for the final answer entry step.

Claros closes this gap. It operates directly on the worksheet: guiding the student through each question via voice, then writing the answer into the correct field only when the student is ready.

## How Claros Works

1. **Upload a worksheet PDF** — Claros parses the document and extracts individual questions into an editable worksheet view.
2. **Start a voice session** — Claros connects to a real-time audio session. The student speaks through their microphone and hears Claros respond naturally.
3. **Discuss a question** — Claros guides the student through the problem using Socratic questioning. It does not give the answer directly. Guided reasoning first, not answer generation.
4. **State the final answer** — The student says their answer out loud (e.g., "I think the answer is 42" or "My answer for question 1 is the Civil War").
5. **Ask Claros to write it** — The student says something like "Write my answer for question 1." Claros confirms, then writes the student's own answer into the correct field on the worksheet.
6. **Export as PDF** — Once finished, the student exports all questions and answers as a formatted PDF.

## Core Product Rule

Claros enforces a deliberate constraint: **it will not write an answer until the student has stated it first.**

- If the student asks Claros to write before they have given their answer, Claros responds: *"Tell me your final answer first, then I can write it into the worksheet."*
- This rule is enforced per question. Stating an answer for question 1 does not unlock writing for question 2.
- The answer readiness gate operates at both the system prompt level (Claros is instructed to refuse) and the backend level (the write pipeline is blocked until the answer is confirmed).

This is an intentional product decision. Claros is designed to support learning, not to bypass it. The voice interface removes the typing barrier; the readiness gate preserves the reasoning requirement.

## Why This Matters

Many students can reason through a problem but struggle to record their answer in a structured format. Claros lets them do the hard part — thinking — with their voice, and handles the mechanical part — typing the answer into the right box — for them.

This is not about making assignments easier. It is about making them accessible to students who already know the material but are blocked by the input method.

## Features

- **PDF assignment ingestion** — Upload any PDF with "Question N:" formatting. Questions are extracted and rendered as an interactive worksheet.
- **Real-time voice conversation** — Bidirectional audio through Gemini Live. The student speaks and hears Claros respond with natural voice.
- **Socratic guidance** — Claros defaults to teaching mode, asking guiding questions rather than stating answers.
- **Per-question answer readiness tracking** — The backend tracks whether the student has stated a final answer for each question before allowing a write.
- **Controlled answer writing** — When permitted, the answer is streamed token-by-token into the correct question field via a separate text generation call.
- **Live transcript** — Both sides of the conversation are transcribed and displayed in real time.
- **PDF export** — Export all questions and current answers as a formatted PDF document.
- **Answer-stated indicator** — The UI shows a visual badge when the backend confirms the student has stated their answer for a given question.

## Architecture

```
Browser (frontend/index.html)
  │
  ├── WebSocket /session/{id} (binary audio + JSON control messages)
  │
FastAPI backend (main.py)
  │
  ├── Gemini Live API (real-time voice: audio in/out, transcription)
  │     via google-genai SDK → models.live.connect()
  ├── Gemini 2.5 Flash (text generation for controlled answer writing)
  │     via google-genai SDK → models.generate_content_stream()
  ├── PDF parser (parser.py — PyMuPDF)
  ├── PDF exporter (exporter.py — ReportLab)
  └── Google Cloud Storage (assignment PDF persistence)
```

**Voice conversation** uses the Gemini Live API through the Google GenAI SDK (`google-genai`). The browser captures microphone input at 16 kHz PCM, sends it over WebSocket, and receives audio responses for playback. Both input and output are transcribed in real time.

**Answer writing** uses a separate Gemini text model (default: Gemini 2.5 Flash) via the same SDK. When a write is triggered, the backend constructs a prompt from the conversation context and the student's stated answer, then streams the generated text to the frontend via `write_start` / `write_token` / `write_end` WebSocket messages.

**Answer readiness gating** is enforced in the backend. A per-question state model tracks whether the student has stated their answer (via heuristic phrase detection on transcribed utterances). Write requests are blocked if the answer has not been confirmed for the target question.

**PDF pipeline**: Uploaded PDFs are stored in Google Cloud Storage, parsed with PyMuPDF to extract questions matching a `Question N:` pattern, and can be exported back as formatted PDFs with answers using ReportLab.

## Google Cloud Deployment

Claros is deployed on **Google Cloud Run** as a containerized service.

- **Container image** is built from the project `Dockerfile` (Python 3.11, FastAPI/Uvicorn).
- **Assignment PDFs** are stored in a **Google Cloud Storage** bucket. The upload endpoint writes to GCS; the voice session and export endpoints read from GCS.
- **Gemini API** calls (both Live and text) are made from the Cloud Run backend using an API key set as an environment variable.
- Cloud Run provides automatic HTTPS, scaling, and a public URL for the frontend.

**Deploying:**

```bash
# Build and push the container (from project root)
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
| Voice AI | Gemini Live API (via Google GenAI SDK) |
| Text AI | Gemini 2.5 Flash (via Google GenAI SDK) |
| PDF parsing | PyMuPDF (fitz) |
| PDF export | ReportLab |
| Storage | Google Cloud Storage |
| Frontend | HTML, CSS, vanilla JavaScript |
| Deployment | Docker, Google Cloud Run |

## Local Setup

**Prerequisites:**
- Python 3.11+
- A Google Cloud project with Cloud Storage enabled
- A Gemini API key
- A GCS bucket for storing uploaded assignments

**Steps:**

```bash
# Clone the repository
git clone <repo-url>
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

Open `http://localhost:8000` in a browser. Upload a PDF or click "Use Test PDF" to load the test assignment, then click "Start Session" to begin a voice conversation.

**Note:** The browser will request microphone access. Use Chrome or a Chromium-based browser for best WebSocket and audio API support.

## Environment Variables

Create a `.env` file in the project root:

```
GEMINI_API_KEY=<your-gemini-api-key>
GCS_BUCKET_NAME=<your-gcs-bucket-name>
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GEMINI_TEXT_MODEL=gemini-2.5-flash
```

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | API key for Google Gemini models (voice and text) |
| `GCS_BUCKET_NAME` | Google Cloud Storage bucket name for storing uploaded PDFs |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project ID |
| `GEMINI_TEXT_MODEL` | Text model used for answer generation (default: `gemini-2.5-flash`) |

Local development may also require Google Cloud application credentials for GCS access (e.g., `GOOGLE_APPLICATION_CREDENTIALS` or `gcloud auth application-default login`).

## Current Limitations

- **Worksheet-focused scope** — Claros works with structured assignments that follow a "Question N:" format. It is not a general-purpose document editor.
- **Heuristic answer detection** — Answer readiness is determined by matching common phrasing patterns (e.g., "my answer is…", "I think it's…"). Unusual phrasings may not be detected.
- **Single-session state** — Answer readiness and conversation context are held in memory per WebSocket session. Refreshing the page starts a new session.
- **PDF format dependency** — Question extraction relies on "Question N:" line patterns. PDFs with different formatting may fall back to single-block extraction.
- **Voice model compliance** — The system prompt instructs Claros to follow specific rules, but LLM compliance is not guaranteed. The backend gate provides a safety net.
- **Basic barge-in** — Claros supports simple interruption: if the user starts speaking while Claros is talking, playback stops and the app returns to listening. This is not full-duplex; there may be a brief overlap before the interruption is detected.
- **Browser compatibility** — Requires a modern browser with WebSocket, AudioContext, and getUserMedia support. Tested primarily on Chrome.

## Future Improvements

- Richer answer detection using a lightweight classifier instead of regex heuristics
- Session persistence so students can resume interrupted sessions
- Multi-format PDF support beyond "Question N:" patterns
- Accessibility audit with assistive technology users
- Full-duplex interruption handling for smoother barge-in
