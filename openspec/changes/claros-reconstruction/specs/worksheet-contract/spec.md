## Purpose

Defines the narrow worksheet contract that lets Claros accept only documents
whose questions and answer areas can be validated deterministically.

## ADDED Requirements

### Requirement: Whole-document validation
Claros MUST validate the complete PDF before creating an assignment. A document
is supported only when it has selectable text, sequential short-answer
questions, and exactly one physically identifiable answer area directly below
each accepted question on the same page and reading column.

#### Scenario: Supported worksheet is accepted
- **WHEN** a PDF satisfies the page, question, geometry, and answer-region limits
- **THEN** Claros creates one assignment containing one question and one answer region per accepted question

#### Scenario: One unsupported question rejects the document
- **WHEN** any required question is ambiguous, remote, choice-based, scanned, or otherwise outside the contract
- **THEN** Claros rejects the entire upload and creates no partial assignment

### Requirement: Stable rejection reasons
The rejection response MUST contain a stable machine-readable reason code and
plain-language guidance that describes the supported worksheet format.

#### Scenario: Unsupported upload explains recovery
- **WHEN** an upload fails validation
- **THEN** the UI shows the reason code's mapped explanation and a path back to upload

### Requirement: Safe client projection
The assignment projection MUST expose only the geometry and evidence needed to
render a preview. It MUST NOT expose signing secrets, storage internals, or
unvalidated client-owned coordinates.

#### Scenario: Assignment projection is returned
- **WHEN** a supported assignment is loaded
- **THEN** the client receives the worksheet title, page count, question prompts, normalized answer-region preview bounds, and source revision hash
