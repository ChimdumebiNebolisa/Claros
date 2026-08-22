## Purpose

Defines the accessible student workflow from upload through question-by-question
completion, optional voice assistance, resume, and honest state presentation.

## ADDED Requirements

### Requirement: Upload and question workspace
The product MUST provide a responsive workspace with the source worksheet as the
visual anchor, one active question at a time, a distinct final-answer editor,
and one primary action for the current state.

#### Scenario: Student opens a supported worksheet
- **WHEN** a supported PDF is accepted
- **THEN** Question 1 opens with the worksheet preview, prompt, final-answer field, and `Review answer` action

### Requirement: Optional voice assistance
Voice MUST remain separate from final-answer authority. Talk-through content
stays in a collapsed or bounded transcript; dictation targets the editable field;
voice cannot commit, export, select geometry, or switch questions silently.

#### Scenario: Voice is unavailable
- **WHEN** microphone permission or speech recognition fails
- **THEN** typed input remains usable, existing draft text remains intact, and a concise recoverable status is shown

### Requirement: Resume without browser secrets
The product MUST restore a valid session through an HTTP-only session cookie or
equivalent server-managed mechanism. Assignment secrets MUST NOT be stored in
`localStorage` or `sessionStorage`.

#### Scenario: Student reloads a valid session
- **WHEN** the browser returns with a valid session cookie
- **THEN** Claros restores the assignment and the last incomplete or active question

### Requirement: Accessible state presentation
Core actions MUST work with keyboard, pointer, semantic labels, visible focus,
reduced motion, and explicit text for errors and placement states.

#### Scenario: Keyboard-only completion
- **WHEN** a student uses Tab, typing, and Enter/Space without a mouse or microphone
- **THEN** upload, editing, review, commit, next question, and export remain reachable and understandable
