## Purpose

Defines the exact-answer, explicit-approval, placement, and commit semantics
that prevent Claros from exporting text the student did not review.

## ADDED Requirements

### Requirement: Exact final answer
Claros MUST preserve the exact Unicode string shown in the final-answer field.
It MUST NOT silently lowercase, correct, paraphrase, strip punctuation, or
replace the student's whitespace while moving text through review and commit.

#### Scenario: Reviewed text is committed exactly
- **WHEN** a student edits capitalization, punctuation, symbols, or apostrophes and reviews the answer
- **THEN** the committed answer text equals the reviewed field value byte-for-byte

### Requirement: Review precedes commit
The system MUST keep draft, review, and committed states distinct. Tutoring
conversation, voice commands, model output, navigation, or stale state MUST NOT
authorize a commit.

#### Scenario: Draft cannot be exported
- **WHEN** a student has typed an answer but has not confirmed the review
- **THEN** the answer is not eligible for export and the UI offers `Review answer`

#### Scenario: Explicit confirmation commits
- **WHEN** a valid placement plan is displayed and the student chooses `Confirm & add`
- **THEN** the server commits only the answer bound to that question and plan token

### Requirement: Placement preflight
Before commit, the server MUST return `fits_in_answer_area`,
`requires_continuation_page`, or `blocked`. A blocked plan MUST be uncommittable;
a continuation plan MUST be disclosed before confirmation.

#### Scenario: Continuation placement is disclosed
- **WHEN** the exact answer exceeds the validated region but can be rendered on a continuation page
- **THEN** review states the continuation behavior before the confirmation action

#### Scenario: Blocked placement cannot commit
- **WHEN** source evidence, question association, or rendering safety no longer validates
- **THEN** commit fails safely and requests a fresh review

### Requirement: Idempotent task-bound commit
Commit MUST be bound to assignment, session, question, exact answer, source revision,
placement result, and expiry. Replaying the same valid commit MUST NOT create a
different answer revision.

#### Scenario: Stale token is rejected
- **WHEN** a plan token is expired, belongs to another question, or belongs to another assignment
- **THEN** the server rejects commit with a recoverable stale-plan error
