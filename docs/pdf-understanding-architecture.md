# Claros PDF understanding architecture

## Decision

Claros keeps the existing PyMuPDF parser as the production default (`PDF_PARSER_MODE=legacy`). Automatic hybrid task approval has a second default-off promotion gate (`ENABLE_DOCUMENT_TASK_AUTO_APPROVE=false`). The candidate path is a feature-flagged hybrid:

1. PyMuPDF opens the original PDF, records page geometry/rotation, extracts reliable native text, discovers physical form fields and drawn answer lines, renders previews, draws evidence overlays, and writes only approved answers back to the original.
2. PP-StructureV3 supplies OCR, layout labels, polygons/boxes, confidence, and reading order for scans or visually structured pages. Its pixel coordinates are normalized to PyMuPDF page points.
3. Gemini uses strict structured output to classify page/block educational meaning and propose student tasks by source block ID. Gemini does not provide or invent coordinates.
4. The intermediate document model validates unique task/block IDs, page references, source provenance, confidence, page roles, review status, and explicit answer-region status before anything reaches the UI.

The PaddleOCR dependency group is isolated in `requirements-paddleocr.txt`; it is not in the synchronous upload image. `ALLOW_SYNCHRONOUS_PADDLEOCR` and `ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS` default to false, so the request path cannot accidentally instantiate either slow candidate stage. A separate parser service or asynchronous job is required before production enablement.

## Resource evidence (2026-07-15)

- Isolated Python 3.11 Paddle environment: 1.10 GiB before model cache.
- Configured model files (document block/layout, mobile detector, English mobile recognizer): about 159 MiB. The local cache reached 769.5 MiB after an earlier table-recognition attempt; table reconstruction is now disabled because Claros needs the detected table region, not HTML reconstruction.
- Warm candidate working set observed during the corpus run: roughly 830-980 MiB. One-page cold/smoke processing took 135-143 seconds; a scan processed in about 35 seconds after initialization.
- Existing Claros Cloud Run service: 1 vCPU, 512 MiB memory, concurrency 80, timeout 3600 seconds. That service shape cannot safely host the measured local pipeline. The parser should use a separate worker/service with low concurrency, explicit memory sizing, persisted job status, and timeout/retry handling.
- Paddle 3.3.1 on Windows required `enable_mkldnn=False`; otherwise PP-StructureV3 failed in the oneDNN executor with an unsupported `ArrayAttribute<DoubleAttribute>` conversion. Linux inference still needs a container-level validation before any parser-worker deployment.

## Current parser behavior

The active legacy parser is `parser.parse_pdf_with_diagnostics`, called by `assignment_service._parse_and_build_manifest` from `POST /upload`.

- It uses `page.get_text("dict", sort=True)` to extract native text lines, font size, one-based page number, and a PyMuPDF top-left rectangle.
- It classifies pages with literal student/teacher/answer-key markers and carries the last class forward across pages.
- It considers `Question 3a:` and `3a.`-style labels, then filters numeric values, scientific notation, URLs, many procedures, and non-question-like bodies.
- It joins nearby extracted lines into a prompt until a question, section boundary, underscore, answer label, or large vertical gap.
- It represents prompt and answer regions as normalized `{x, y, width, height}` fractions of the page. The newer intermediate model additionally preserves `[x0, y0, x1, y1]` PDF points.
- It accepts underscores and sufficiently long vector horizontal lines as strong answer evidence. It can also propose whitespace between questions or explicit “write below” page-end space; low-confidence or mixed layouts are review-gated.
- Selectable PDFs use native text only. Image-only scans have no line records and return `requires_ocr` with zero invented questions.

Known false-positive/unsafe areas remain: marker-based page classification is incomplete, numbered procedure/reference content can still pass linguistic filters, native `sort=True` is not a general multi-column reading-order solution, and whitespace answer proposals are less reliable than explicit physical fields/lines. The legacy parser remains intact for comparison and rollback.

## Intermediate model and safety invariants

`document_model.py` defines `IntermediateDocument`, `DocumentPage`, `DocumentBlock`, and `DocumentTask`. Page roles are `teacher_guide`, `student_worksheet`, `answer_key`, `reference_material`, `mixed`, and `unknown`.

Every candidate task has:

- a deterministic stable string ID plus a compatibility numeric question ID;
- zero-based page index and page role;
- prompt text and source block IDs on the same page;
- prompt geometry when available;
- confidence and review status;
- an answer-region status: `detected`, `approved`, `missing`, `low_confidence`, or `side_panel`.

Writable coordinates are accepted only from explicit physical `form_field` or `answer_line` blocks with sufficient confidence, or from an explicit teacher/student review adjustment validated inside the page. A missing region becomes `side_panel`; it never becomes guessed whitespace. Export preserves all original pages and appends confirmed side-panel answers when no approved writable region exists.

## Semantic validation

`semantic_classifier.GeminiSemanticClassifier` reuses `GEMINI_API_KEY` and `GEMINI_TEXT_MODEL`. It sends extracted block IDs, layout labels, reading order, PDF-point boxes, confidence, page context, and a rendered page image when layout requires it. It does not log document text or provider output.

The structured result is rejected unless it:

- validates against the strict Pydantic/JSON schema;
- returns the requested page index;
- classifies every extracted block exactly once;
- references only real same-page block IDs;
- returns no tasks for non-student page roles;
- provides non-empty task prompt text.

Rejected output produces an unknown page, zero tasks, and a review warning.

## Teacher and student flows

- `POST /upload?review_mode=teacher` creates a draft manifest. The teacher UI and `/api/teacher/assignments/{id}/review` support accept, edit, merge, split, hide, reject, and finalization. Finalization fails while tasks remain unresolved.
- Student session loading filters teacher-mode manifests to approved tasks only.
- Direct student uploads can auto-approve only high-confidence student-worksheet tasks with high-confidence physical answer evidence. Other tasks remain reviewable or use the side panel.
- The existing confirm-before-write token contract remains. The write endpoint still refuses absent or unresolved regions; side-panel answers bypass PDF-coordinate writing and are appended safely at export.

## Reproducible benchmark

Run the current/native evidence pass:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_pdf_pipeline.py `
  --corpus C:\Users\Chimdumebi\Downloads\claros-pdf-acceptance-corpus\claros-pdf-corpus `
  --out output\pdf-benchmark-current
```

Run the isolated Paddle candidate after installing `requirements-paddleocr.txt` into Python 3.11:

```powershell
$env:PADDLE_PDX_MODEL_SOURCE='bos'
python scripts\benchmark_pdf_pipeline.py --corpus <corpus> --out output\pdf-benchmark-paddle `
  --paddle --paddle-all-pages
```

Add `--semantic` only when the existing Gemini secret is intentionally available. The report writes JSON, CSV, Markdown, and page overlays. Missing/merged/false-positive fields remain explicitly manual until fixed task-level gold annotations exist; count deltas are not mislabeled as precision or recall.
