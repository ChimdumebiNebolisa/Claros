## Purpose

Defines safe derivative PDF generation from the immutable source and committed
answers, with source and placement revalidation before bytes are returned.

## ADDED Requirements

### Requirement: Export only committed answers
Export MUST use the immutable original source, current validated evidence, and
committed answers only. Drafts, transcript messages, and unreviewed model output
MUST never appear in the exported PDF.

#### Scenario: Complete worksheet exports
- **WHEN** every question has a valid committed answer and source evidence is unchanged
- **THEN** Claros returns a new PDF derivative and leaves the original source unchanged

#### Scenario: Incomplete worksheet cannot export
- **WHEN** one or more questions have no committed answer
- **THEN** export fails with a recoverable message and no derivative is returned

### Requirement: Placement plan is honored
Export MUST reproduce the approved answer-area or continuation-page placement.
If the approved plan can no longer be honored, export MUST fail rather than
silently rerouting the answer.

#### Scenario: Source revision mismatch
- **WHEN** the source hash or question-to-region evidence changes after commit
- **THEN** export fails and asks the student to review the affected answer again

### Requirement: Safe rendering failure
If the renderer cannot reproduce an approved answer safely, export MUST return a
recoverable error and preserve the committed answer for editing.

#### Scenario: Unsupported glyph
- **WHEN** an answer contains a glyph the active renderer cannot safely embed
- **THEN** export fails explicitly without mutating committed answer state
