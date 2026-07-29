# Claros PDF understanding benchmark report

> **Historical benchmark snapshot (2026-07-15).** Promotion advice and
> “legacy as production default” conclusions below are investigation-era, not
> present-tense Claros runtime claims. Current defaults: see
> [`ARCHITECTURE.md`](ARCHITECTURE.md) and `config.py` (`PDF_PARSER_MODE=hybrid`).

**Date:** 2026-07-15
**Corpus:** `C:\Users\Chimdumebi\Downloads\claros-pdf-acceptance-corpus\claros-pdf-corpus`
**Scope:** 20 PDFs, 109 pages, including 17 selectable PDFs and 3 image-only scans
**Deployment:** none

## Decision (investigation-era)

**Do not promote PP-StructureV3/Gemini as the production default.** Keep the corrected legacy parser as the default, keep the hybrid behind default-off feature flags, and move any future Paddle/Gemini execution to an asynchronous low-concurrency parser worker. Require teacher review for mixed packets, scans, forms/tables, and any task without a reviewed response region.

Paddle physical extraction is useful: all three image-only scans produced ordered layout/OCR blocks, and the numbered scan produced the expected four prompts after Gemini classification. The promotion blocker is semantic precision and task granularity, not scan recovery. Across the 17 PDFs with expected counts, the final staged candidate emitted 201 tasks for 136 expected and matched the expected count on only 3/17 PDFs. Count matches are not precision/recall; task-level gold spans do not exist for this corpus.

## Architecture implemented

- The existing PyMuPDF parser remains available and is still the production default.
- PyMuPDF remains responsible for native geometry/text, page rendering, preview overlays, explicit form/line evidence, original-PDF answer writing, and export.
- `PaddleOCRAdapter` wraps PP-StructureV3 behind a lazy boundary, accepts PDF pages or standalone page images, preserves page/rotation/reading order/provenance, and converts pixel coordinates to PDF points.
- A strict intermediate model represents documents, pages, blocks, page roles, tasks, prompt/response regions, confidence, review state, and source block IDs.
- Gemini reuses the existing API key/model conventions and returns strict structured page/block/task decisions. Invalid output is rejected to an unknown/review state without logging document content.
- Automatic hybrid task approval, synchronous Paddle, and synchronous Gemini semantics are independently default-off.
- Teacher review supports accept, edit, merge, split, hide, reject, and finalization. Teacher-mode student loading exposes approved tasks only.
- Missing/unreviewed regions use a side panel. Export writes a manifest region only when it is reviewed or the current student explicitly confirms a region; otherwise it preserves the original pages and appends the confirmed answer.

See `docs/pdf-understanding-architecture.md` for model and flow details.

## Current parser behavior

The active legacy parser extracts native lines from `page.get_text("dict", sort=True)`, applies teacher/student/answer-key marker heuristics, recognizes question/compound-number patterns, joins nearby continuation lines, and emits normalized top-left regions. Explicit underscores and vector lines are its strongest answer evidence; whitespace/page-end proposals are lower confidence and are review-gated. It does not OCR scans, which now return `requires_ocr` with zero invented tasks.

Remaining legacy failure modes are incomplete page-role classification, numbered procedure/reference false positives, missed unnumbered/image questions, non-general multi-column reading order, and unsafe whitespace adjacency if confidence gating is bypassed. The corrected baseline suppresses those regions rather than writing them.

## Benchmark summary

The full reproducible table is at `output/pdf-benchmark-final/comparison.md`; JSON and CSV variants are in the same directory. The comparison is intentionally staged: the Paddle physical pass and Gemini semantic pass were measured separately across the full corpus, with combined Paddle+Gemini overrides for all three image-only scans.

| Metric | Current parser | Staged candidate |
|---|---:|---:|
| PDFs/pages processed | 20 / 109 | 20 / 109 |
| Count-labeled PDFs | 17 | 17 |
| Expected tasks on count-labeled PDFs | 136 | 136 |
| Emitted tasks on count-labeled PDFs | 99 | 201 |
| Expected-count matches | 2/17 | 3/17 (PDFs 12, 16, 18) |
| Student launch-subset expected-count matches | 2/5 | 0/5 |
| Image-only numbered scan | `requires_ocr`, 0 tasks | 5 Paddle blocks, 4 review-gated tasks |
| Candidate tasks auto-approved | n/a | 0/224 |
| Candidate answer status | n/a | 44 detected, 8 low-confidence, 172 side-panel |
| Paddle blocks | n/a | 602 |
| Physical-stage time | ~13.1 s legacy parse sum | ~4,510.6 s staged Paddle sum |
| Semantic-stage time | n/a | ~1,836.2 s with scan overrides |

Notable observations:

- PDF 02: semantics recovered the two prompts missed by the current parser, but emitted 13 tasks for 12 expected.
- PDF 12: page roles correctly separated teacher-guide and answer-key pages and reduced 33 current records to 16, but two pages still depended on OCR in the separate semantic stage.
- PDF 18: combined Paddle+Gemini recovered all four visible scan prompts. Every answer remained side-panel because the scan has no explicit writable response region.
- PDF 01: one expected activity became six form-field tasks. The physical lines were real, but semantic task granularity was wrong.
- PDFs 07, 09, 13, 14, 15, 17, 19, and 20 substantially over-produced tasks. Numbered-line false positives were reduced on classified teacher/answer-key pages but not solved globally.

## Question precision and recall

Numeric precision/recall is **not reportable** because the corpus supplies expected counts, not gold prompt spans and labels. Count deltas cannot distinguish false positives from simultaneous missing/merged/split tasks. The available evidence is:

- corrected legacy strict exact-set result: 2/17 selectable PDFs;
- candidate expected-count match: 3/17 count-labeled PDFs;
- candidate total overage: 201 emitted versus 136 expected on count-labeled PDFs;
- visual examples show both genuine recovery (PDF 18) and semantic over-splitting/false tasks (PDFs 01 and 07).

## Answer-region accuracy

No task-level gold response rectangles exist, so a numeric accuracy rate is not claimed. The safety result is concrete:

- only explicit PDF form fields/answer lines can become writable physical evidence automatically;
- table grids/decorative rules remain non-writable candidates;
- 76.8% of candidate tasks used side-panel fallback, 3.6% were low-confidence, and 19.6% had detected physical regions;
- the promotion gate left all 224 candidate tasks review-required;
- invalid/unreviewed manifest regions are not used by export unless the student explicitly confirms a valid normalized region;
- overflow or missing regions append the full confirmed answer instead of truncating it or guessing coordinates.

## OCR, performance, and Cloud Run

- PP-StructureV3 recovered 4, 16, and 5 blocks on the three scans in about 35.1 s, 43.9 s, and 50.6 s for the physical stage.
- Combined scan results were 1 task (table worksheet, low-confidence region), 1 aggregate matching task (side panel), and 4 numbered questions (all side panel).
- Paddle document median was ~115.9 s; maximum was ~895.3 s for the 16-page image-heavy packet. Dense native packets are therefore not suitable for synchronous upload.
- The isolated Paddle Python environment was ~1.10 GiB; configured model files were ~159 MiB. Peak RSS growth was ~679 MiB and observed working set approached 1 GiB.
- The existing Cloud Run service is 1 vCPU, 512 MiB, concurrency 80, timeout 3600 seconds. It cannot safely host the measured parser.
- Windows Paddle 3.3.1 required oneDNN to be disabled; Linux container inference remains unverified.

## Visual evidence

- Current parser: `output/pdf-benchmark-current` (109 overlays)
- Paddle physical: `output/pdf-benchmark-paddle-hybrid-2` plus `output/pdf-benchmark-paddle-rectangles` (109 full-pass overlays plus corrected form overlays)
- Gemini semantic: `output/pdf-benchmark-semantic-full` (109 overlays)
- Combined scans: `output/pdf-benchmark-scans-combined` (3 overlays)

Overlay colors are gray native/physical blocks, purple Paddle blocks, green explicit physical response evidence, magenta current-parser prompts, red final prompts, blue final answer regions, and orange review-required tasks.

## Verification

- Python and coverage gate: 181 tests passed at 80.09% coverage (required: 72%).
- Frontend session/UI/contract suite passed.
- Ruff and Python byte-compilation passed.
- Docker image built and `/health` returned 200 after adding the review service to the image.
- Both live Claros URLs returned 200 for `/health`; no parser deployment was performed.

## Deployment status and remaining work

No deployment was attempted because the promotion criteria were not met. The project-number URL and `https://claros-fnaobzrxeq-uc.a.run.app/` resolve to the same `claros` Cloud Run service in project `claro-490122` (project number `505797934944`), revision `claros-00045-9pt`; the latter is not a stray service and must not be deleted.

Remaining work:

1. Create task-level gold annotations (prompt/source/response rectangles) and manually score missing, merged, split, and false-positive tasks.
2. Improve semantic aggregation and page-context handling, especially forms, objectives, tables, and multi-part prompts.
3. Implement an asynchronous parser worker/job protocol and validate a Linux Paddle container with appropriate memory and concurrency.
4. Add authenticated teacher authorization around review routes; the current flow follows the repository's existing assignment-ID access convention.
5. Run browser/microphone/accessibility E2E and live upload/write/export checks only after a non-production revision is intentionally deployed.

## Recommendation

Keep the current parser as production default with the existing safety corrections. Continue the native-PDF + selective Paddle + Gemini hybrid behind flags, use Paddle first for scans and layout-heavy pages in a separate worker, and require teacher review for mixed packets/scans/forms until task-level precision materially improves. Do not investigate Docling yet: the measured blocker is semantic task definition and runtime architecture, not inability to recover scan text/layout.
