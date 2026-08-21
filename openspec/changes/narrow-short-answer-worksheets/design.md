# Design: Supported short-answer worksheet module

## Seam

The production seam is `parse_supported_worksheet(...)`. It is a deep module:
callers provide PDF bytes and the existing extraction/classification adapters,
and receive either one canonical, explicitly supported document or a typed
controlled rejection. Callers do not interpret confidence, page roles,
response types, or geometry themselves.

`parse_document(...)` remains the lower-level physical/evaluation module. It
can represent broader evidence so unsupported structures can be recognized and
measured, but the assignment upload path no longer treats its output as a
product-ready worksheet.

## Supported contract

- PDF only; one through eight pages; one through forty questions.
- Questions use source-backed native text and normal top-to-bottom reading
  order. Wrapped lines may form one question when their geometry is contiguous.
- Each question has one local response space or one vertically aligned group
  of blank answer lines on the same page.
- Response geometry is an approved native PDF line, blank bounded rectangle,
  blank writable area, or text form field.
- Every response region is below its question and before the next question on
  that page. No region may be shared, overlap another region, or skip an
  intervening question or unclaimed writable space.
- Page transitions occur only between complete question/response pairs. A
  question may be near a page edge, but its answer space may not continue on
  another page.

## Rejection model

`WorksheetClassification` records the contract version, outcome, stable reason
codes, question count, and provider-call count. Ambiguity includes missing or
unapproved geometry, cross-page links, extra writable spaces, uncertain page
or task status, and non-linear ordering. Unsupported structure includes
choices, checkboxes, tables, drawings, essay/long-text tasks, answer keys,
teacher guides, remote answer sections, and transformed or OCR-only write
geometry. Workload-limit failures are controlled unsupported results.

The upload endpoint returns HTTP 422 with code
`UNSUPPORTED_WORKSHEET_FORMAT`, a stable classification, reason codes, and a
plain-language explanation. No assignment is persisted.

## Authority

Gemini may select only supplied source blocks and response candidates to help
recognize questions. It cannot create IDs, text, coordinates, response areas,
or write authorization. Deterministic code reconstructs text, verifies page
geometry and association, classifies the whole worksheet, issues write tokens,
and performs PDF changes. Any disagreement resolves to rejection.

## Workload and cost

The service rejects PDFs over eight pages before classification. A semantic
adapter declares whether a page classification consumes a provider call. The
pipeline preflights the eight-call budget and increments it before each call,
so a mock or provider cannot exceed the ceiling. Question count is checked as
results arrive and at final classification. Gemini requests use a fifteen-
second transport timeout and one attempt. Cloud Run is limited to two
instances and one concurrent upload per instance.

## Retained architecture

- Canonical pages/blocks/tasks/regions: retained for provenance and validation.
- Native/vector response extraction: retained because it establishes physical
  write evidence.
- Closed-world semantic adapter: retained only for question recognition among
  supplied evidence.
- Confirmation, single-use write token, and exporter: retained unchanged as
  the authoritative answer-integrity path.
- Side-panel export: retained for deterministic overflow after an accepted
  physical target, not as document-format acceptance or speculative placement.
- OCR adapter and review model: retained as non-production evaluation and
  legacy compatibility seams; OCR-only or review-required uploads reject.
