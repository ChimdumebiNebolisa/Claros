# Claros audit record

> **Historical public-claim audit (updated 2026-07-12).** Superseded as a
> present-tense architecture diagram. Current flow:
> [`ARCHITECTURE.md`](ARCHITECTURE.md) and the README architecture section.

Updated: 2026-07-12

## Active producer-to-consumer flow (as of 2026-07-12)

```mermaid
flowchart LR
  Browser[Browser] --> Landing[GET / → frontend/landing.html]
  Browser --> App[GET /app → frontend/app.html]
  App --> Upload[POST /upload]
  Upload --> Parser[PyMuPDF parser]
  Parser --> Manifest[AssignmentManifest]
  Manifest --> GCS[(Google Cloud Storage)]
  App --> Start[POST /api/session/start]
  Start --> Session[session_service]
  Session --> GCS
  App --> Config[GET /api/session-config/{assignment_id}]
  Config --> Token[Gemini ephemeral token]
  App --> Live[Direct browser Gemini Live]
  App --> Confirm[POST /api/session/{id}/confirm]
  Confirm --> TokenStore[Single-use write token]
  App --> Write[POST /api/write/{assignment_id}]
  Write --> Gemini[Gemini text stream]
  Write --> Worksheet[Question answer field]
  App --> Export[POST /export/{assignment_id}]
  Export --> PDF[ReportLab PDF]
```

## Storage and lifecycle findings

| Data | Producer | Consumer | Current lifecycle | Remaining hardening |
| --- | --- | --- | --- | --- |
| Assignment PDF | `/upload` → `upload_pdf_to_gcs` | manifest backfill, export, delete | Explicit delete only; manifest carries an expiry timestamp | Enforce expiry and cleanup policy |
| Assignment manifest | parser → `upload_manifest_to_gcs` | session start, config, write, export, diagnostics | Stored beside the PDF | Reject expired manifests consistently |
| Session state | `/api/session/start` → `upload_session_to_gcs` | confirm, restore, write-token validation | Session expiry is checked on load; explicit session deletion is not exposed | Add generation preconditions and cleanup |
| Write token | confirm → session blob | write endpoint | Removed after validation and recorded as used | Test concurrent validation and stale writes |

## Public-claim audit

- Verified: no account flow exists; active pages are `/` and `/app`; confirmation is required before the write endpoint accepts a token; microphone capture is started only from the session control; export is available through the button and voice intent.
- Corrected: the landing FAQ no longer claims answers remain only in the browser. Assignment PDFs and session state are persisted in configured storage.
- Corrected: public copy now says selectable-text PDFs work best and image-only scans may need OCR. `ENABLE_OCR` is currently disabled by default and no OCR provider is wired into the upload path.
- Not claimed: automatic deletion, guaranteed retention duration, certifications, complete scanned-PDF support, provider-level privacy guarantees, or “AI never writes” beyond the enforced confirmation/token path.

## Known gaps selected for later slices

- Manifest `expires_at` is created but must be enforced in every assignment-consuming route.
- Session writes currently use unconditional GCS uploads; generation-aware preconditions are required to prevent lost updates.
- Operational metrics are not yet standardized as content-free events.
- Legacy frontend prototypes have been removed after route/build/reference checks; only `frontend/landing.html` and `frontend/app.html` are active entrypoints.
