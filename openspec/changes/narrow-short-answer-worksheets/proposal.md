# Change: Narrow Claros to sequential short-answer worksheets

## Why

Claros currently materializes generalized worksheet tasks and then routes
uncertain structures to review or a side panel. That behavior is broader than
the product can defend. The active product should accept only PDF worksheets
whose questions and local blank response regions can be associated in normal
reading order by deterministic geometry.

## What changes

- Add a production worksheet-classification seam with explicit supported,
  ambiguous, and unsupported outcomes.
- Accept only sequential short-answer or numeric questions with local blank
  lines, line groups, form fields, or blank boxes.
- Reject unsupported or ambiguous layouts as a controlled upload result; do
  not promote them through review, confidence, or side-panel parsing fallbacks.
- Bound uploads to eight pages, forty questions, and eight semantic provider
  calls, with one provider attempt and a fifteen-second request timeout.
- Retain the canonical physical document model, deterministic association,
  confirmation/write authorization, exporter, and overflow side panel because
  they enforce the write-safety contract after a document is accepted.
- Harden tutoring prompts, private response caching, deployment configuration,
  evaluation vocabulary, container privileges, and generated frontend output.

## Non-goals

- Arbitrary-document support, multiple choice, answer tables, answer keys,
  remote answer sections, essays, or complex multi-column layouts.
- A distributed quota platform or broad storage-lifecycle redesign.
- A frontend visual redesign or a rewrite of the PDF geometry engine.

## Impact

- New production uploads fail closed when the narrow contract is not proved.
- Historical/evaluation adapters may still construct the canonical document
  model, but they are no longer an acceptance path for new assignments.
- Product samples, evaluation fixtures, documentation, and deployment settings
  align with the narrower boundary.
