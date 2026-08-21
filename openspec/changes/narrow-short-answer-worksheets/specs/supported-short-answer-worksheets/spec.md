## ADDED Requirements

### Requirement: Production accepts only the supported worksheet class

Claros SHALL accept only PDF worksheets with sequential source-backed
short-answer questions and deterministic local blank response geometry. It
SHALL classify every production upload as supported, ambiguous, or unsupported
before persisting an assignment.

#### Scenario: Sequential question and local blank are supported

- **WHEN** each question is followed on the same page by one blank line, an
  aligned group of blank lines, a blank text field, or a blank rectangle before
  the next question
- **THEN** the worksheet is classified as supported and every task retains only
  its deterministic response evidence

#### Scenario: Relationship is ambiguous

- **WHEN** a response area could belong to more than one question, crosses a
  page, skips an intervening question, or an extra writable space is unclaimed
- **THEN** the entire upload is rejected with an ambiguous classification and
  no assignment is persisted

#### Scenario: Structure is unsupported

- **WHEN** the document contains multiple choice, a write-in table, an answer
  key, a remote answer section, an essay area, a complex two-column layout, or
  another unsupported task structure
- **THEN** the entire upload is rejected with an unsupported classification
  instead of review or speculative fallback

### Requirement: Geometry remains authoritative

AI semantics SHALL only assist recognition among supplied physical evidence.
Only deterministic geometry, association validation, student confirmation,
and server authorization may permit a write.

#### Scenario: Model proposes unsupported placement

- **WHEN** semantic output selects a missing, cross-page, overlapping,
  unapproved, or invented response target
- **THEN** deterministic validation rejects the worksheet and no model output
  becomes write authority

### Requirement: Workload is bounded

Claros SHALL reject PDFs over eight pages, worksheets over forty questions, or
uploads requiring more than eight semantic provider calls. Each provider call
SHALL have a fifteen-second timeout and at most one attempt.

#### Scenario: Provider-call budget would be exceeded

- **WHEN** classifying an upload would require a ninth semantic provider call
- **THEN** Claros rejects before making that call and the observed call count
  remains at or below eight

### Requirement: Protected worksheet content is non-cacheable

Capability-protected assignment pages, session content, writes, and exports
SHALL send `Cache-Control: private, no-store`.

#### Scenario: Protected page is fetched

- **WHEN** an authorized client fetches a worksheet page or session response
- **THEN** the response is usable by that client and carries the private,
  no-store cache policy

### Requirement: Worksheet text cannot instruct the tutor

Worksheet content SHALL be treated as untrusted quoted data in tutoring prompt
construction. Instructions embedded inside it SHALL NOT supersede Claros's
trusted tutoring, confirmation, or write rules.

#### Scenario: Worksheet contains prompt injection

- **WHEN** worksheet text says to ignore Claros rules or write without student
  confirmation
- **THEN** the trusted system prompt identifies that text as worksheet data and
  deterministic confirmation/write authorization remains unchanged
