# Worksheet layout preservation

Claros keeps the original worksheet PDF as the primary working surface.

## Manifest v2

New assignments persist `manifest.json` version **2** with:

- `pages[]`: page index, width/height in PDF points, `has_usable_text`, `requires_ocr`
- `questions[]`: existing `id`/`text` plus `page_index`, `question_bbox`, `answer_bbox`, `layout_confidence`, `layout_warnings`

Coordinate system: **PDF points, origin at the top-left of each page** (PyMuPDF page space). Rectangles are `[x0, y0, x1, y1]`.

Legacy manifests (v1) remain readable. They are upgraded **in memory only** with `legacy_manifest_v1` / `missing_layout_regions` warnings. Stored objects are not rewritten solely to bump versions.

## Region detection (supported)

Conservative geometry heuristics:

1. Detect `Question N:` / `Question N.` or numbered `N.` / `N)` labels.
2. Union nearby text rectangles in the same column.
3. Propose the space below the prompt and before the next item as the answer region.
4. Reject undersized, overlapping, cross-column, or cross-page guesses and mark them `low` / unresolved.

Supported layouts in this vertical slice:

- One-column worksheets
- Multiline question blocks
- Two-column worksheets (no cross-column merging)
- Multi-page worksheets
- Table-like numbered items with printable answer lines
- Unicode math/punctuation normalization

Known unsupported / weak cases:

- Arbitrary floating forms without question labels
- Dense multi-column newspapers
- Handwritten answer boxes without extractable text anchors
- Scanned/image-only pages (OCR required)

## OCR-required state

Image-only pages set `requires_ocr: true` and stay in the manifest. Claros does **not** invent a fake `Question 0` for scans. The UI shows a recoverable status. `ocr_adapter.py` defines the adapter boundary; production OCR is intentionally out of this PR (`ENABLE_OCR` remains off by default).

## Answer entry UI

The worksheet view renders each original page preview and overlays accessible answer fields at detected regions. Low-confidence or unresolved regions are announced in status text. Layout correction mode lets students move/resize/reset regions; corrections stay in client state and are sent as `layout_overrides` with export.

## Export

Primary export opens the **original PDF** and inserts answers into resolved regions (including manual overrides). Unanswered questions are left blank. Answers that do not fit or lack a resolved region return **422** with the affected question ids. The ReportLab reconstructed exporter remains only as a legacy fallback for manifests without usable layout metadata.

## Preview API

`GET /api/assignments/{assignment_id}/pages/{page_index}/preview` returns a bounded PNG for the original page. Requests respect assignment expiry, page bounds, DPI limits, and a maximum pixel budget. Previews are not persisted.
