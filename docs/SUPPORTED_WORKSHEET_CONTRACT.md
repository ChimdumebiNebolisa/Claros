# Supported worksheet contract

Claros supports one bounded document class: PDF worksheets made of sequential
short-answer questions, each followed by its own physically identifiable blank
response space.

The only production sample currently advertised under this contract is
`canonical-short-answer-ecosystems`. Choice and multi-region math documents are
retained as deterministic rejection fixtures, not product samples.

## Question

A question is one source-backed native PDF text block, or a tightly wrapped
sequence of native text blocks, that asks for one short written or numeric
response. The semantic classifier may identify which supplied blocks form the
question. Claros reconstructs the visible wording from those blocks and never
uses model-authored wording as source text.

Brief explanation prompts are supported when their response space remains a
small, local blank box. Essay prompts, arbitrary long-form areas, selections,
checkboxes, drawings, and table-cell tasks are unsupported.

## Answer-region geometry

Accepted evidence is one of:

- a visible blank answer line;
- a vertically aligned group of visible blank answer lines;
- a visibly blank bounded rectangle or writable area; or
- a blank text form field.

The geometry must be native deterministic PDF evidence, fully inside the page,
non-overlapping, untransformed, and approved by the existing blankness and
visibility checks. A response space may be no more than 180 PDF points tall;
larger long-form/essay areas reject. OCR text or model output can never create
writable geometry.

## Association and order

Questions use normal top-to-bottom reading order. Every answer region must:

1. be on the same page as its question;
2. begin after the question's final source block;
3. begin no more than 120 PDF points below the question;
4. end before the next question on that page;
5. remain in the same reading column;
6. belong to only that question; and
7. leave no competing or unclaimed writable space in the interval.

Line groups must be vertically ordered, horizontally aligned, and contain no
intervening text or graphics. Multiple templates are allowed when they satisfy
these rules; no exact page template is hardcoded.

## Page boundaries

A worksheet may contain up to eight pages and forty questions. A question may
appear near the bottom of a page, but its complete response space must stay on
that page. Page transitions occur only between complete question/response
pairs. Cross-page prompts or remote answer sections are ambiguous and reject.

## Rejection

The whole upload rejects when Claros cannot prove this contract. Stable reasons
cover missing or uncertain geometry, cross-page relationships, non-linear or
multi-column order, extra writable spaces, unsupported response types,
answer-key/teacher content, OCR-only write evidence, transformed pages, and
workload limits. Rejection is success for an unsupported document: Claros does
not escalate through increasingly speculative fallbacks.

The classifier records `supported`, `ambiguous`, or `unsupported`. Only
`supported` documents cross the assignment-creation boundary. Both ambiguous
and unsupported uploads return the controlled HTTP 422 code
`UNSUPPORTED_WORKSHEET_FORMAT`, include stable reason codes, and create no
writable assignment.

## Authority

Gemini semantics can select supplied prompt and response-candidate IDs to help
recognize the supported class. Deterministic code owns source text,
coordinates, question/region association, whole-document support
classification, student confirmation, write-token issuance, overflow, and PDF
changes. A semantic result can cause rejection; it cannot independently grant
permission to write.

Claros writes only the student's exact confirmed answer to a response region
authorized for that question. The export side panel remains available only for
deterministic overflow after an accepted target; it is not an acceptance path
for unsupported worksheet layouts.
