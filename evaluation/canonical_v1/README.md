# canonical_v1 first-party worksheets

`canonical_v1` is the initial deterministic PDF parser milestone. It contains
three student-facing worksheets created by Claros:

- **Short Answer** — *Introduction to Ecosystems*
- **Multiple Choice** — *Digital Safety Basics*
- **Math Practice** — *Everyday Math*

These are also product-quality sample worksheets for a future “Try a sample
worksheet” entry point. Frontend wiring is intentionally out of scope here.

The first-party source specification is authoritative. These labels are
deterministic expected data produced with the PDFs; they are not human labels,
AI-adjudicated silver, or machine predictions. No Label Studio pass is needed.

## Files and regeneration

- `source.json` — one semantic definition for all worksheet content, task IDs,
  task types, choices, responses, and page breaks.
- `schema.py` — strict source and generated-manifest contracts.
- `generate.py` — deterministic ReportLab renderer. It records each prompt and
  physical response rectangle while drawing it, then writes PDFs, previews,
  hashes, page roles, and prompt-to-response relations.
- `evaluate.py` — Stage 3 acceptance harness. It runs
  `document_pipeline.parse_document` against the checked-in PDFs, selects only
  among extracted physical evidence, and scores the unchanged expected labels.
- `generated/manifest.json` — exact expected semantic structure and PDF-point
  geometry for the generated assets.
- `generated/pdfs/` — selectable-text sample PDFs.
- `generated/rendered/` — 144-DPI-equivalent visual inspection previews.
- `generated/baseline.json` — Stage 3 `parse_document` results against the
  expected labels.
- `generated/baseline_legacy_parser.json` — preserved pre-Stage-3 legacy
  `parse_pdf_with_diagnostics` baseline for provenance.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m evaluation.canonical_v1.generate
.\.venv\Scripts\python.exe -m evaluation.canonical_v1.evaluate
.\.venv\Scripts\python.exe -m pytest tests\test_canonical_v1.py -q
```

Generation uses PDF points with a top-left origin in the manifest and stable
IDs from `source.json`. ReportLab invariant mode makes repeated PDF builds
byte-identical. PyMuPDF renders the previews and verifies selectable text in
tests.

## Baseline metric contract

The report includes:

- task-count accuracy and exact-count document rate;
- normalized prompt-text fidelity;
- task-order accuracy;
- one-to-one response-region detection using at least 50% expected-region
  coverage (one parser region cannot satisfy multiple expected regions);
- mean response-region IoU, which exposes over-broad regions separately;
- response-type accuracy against Stage 3 region types;
- task-to-response association accuracy after deterministic validation;
- physical-response detection against extracted `pdf_geometry` candidates
  before/alongside task materialization;
- false-positive task and writable-region counts.

Expected labels in `source.json` / `generated/manifest.json` are never altered
to improve scores. Offline evaluation may select among Stage 3-extracted
physical blocks using expected prompt text and geometry coverage; it does not
invent coordinates and is not a substitute for live Gemini verification.

## Scope boundary

`canonical_v1` is independently runnable and is the first parser milestone.
The external PDF acceptance corpus and historical 17-page pilot remain
preserved as later real-world stress suites. Passing these three controlled
documents is not evidence that arbitrary worksheets, scans, tables, mixed
packets, or image-dependent tasks are solved.
