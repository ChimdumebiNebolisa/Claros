## Purpose

Preserve Claros's existing worksheet safety and interaction contract while its
landing and workspace presentation are substantially reorganized.

## ADDED Requirements

### Requirement: Answer integrity remains server-authorized

Claros SHALL bind drafts, confirmations, and writes to the exact task and
response target; SHALL require explicit confirmation before writing; SHALL use
the server-issued single-use token; and SHALL preserve the exact approved text.

#### Scenario: Student confirms without writing

- **WHEN** the student submits an exact task/target answer to confirmation
- **THEN** the response enters confirmed/not-written state and no worksheet
  bytes are changed until the separate write action occurs

#### Scenario: Write is attempted without valid authorization

- **WHEN** the client lacks a matching session credential or single-use token
- **THEN** the server rejects the write and the UI presents a recoverable state
  without claiming that the answer was written

### Requirement: Typed operation and optional voice are preserved

The system SHALL keep the typed path complete without microphone access and
SHALL treat voice as an optional transport that cannot bypass confirmation or
write authorization.

#### Scenario: Voice is unavailable

- **WHEN** microphone permission, provider loading, credentials, or live
  connection is unavailable
- **THEN** the user can still type, review, confirm, write, and export through
  the keyboard/pointer path

### Requirement: Safe placement and export remain deterministic

The system SHALL preserve server-owned physical evidence, unsafe-target
side-panel fallback, original-page preservation, and authorized export of
written answers only.

#### Scenario: Unsafe target is exported

- **WHEN** a confirmed answer is written for a target that cannot safely receive
  physical text
- **THEN** the original page remains unchanged and the answer appears in the
  labeled export side panel with task context

#### Scenario: Export has no written answers

- **WHEN** the user requests export before any answer is confirmed and written
- **THEN** the request is rejected with an honest recoverable message and no
  empty-success download is presented

### Requirement: Restore and recovery remain truthful

The system SHALL restore valid partial session state and SHALL demote or clear
expired, mismatched, or source-changed state rather than reusing stale
confirmation or write authorization.

#### Scenario: Page refresh follows partial completion

- **WHEN** a valid session pointer exists and the user reloads the workspace
- **THEN** valid drafts, response states, active task, and active target return
  through the restore contract

#### Scenario: Session or source is stale

- **WHEN** restore or a write detects expired credentials or changed source
- **THEN** the UI explains recovery, does not write, and requires a fresh
  authorized path
