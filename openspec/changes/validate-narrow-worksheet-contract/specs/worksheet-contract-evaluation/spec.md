## Purpose

Provides deterministic evidence that the narrow worksheet contract accepts
realistic supported variation and rejects ambiguous or unsupported layouts.

## ADDED Requirements

### Requirement: Evaluation uses a substantial first-party fixture corpus
The contract evaluation SHALL use 20–30 deterministic, repository-controlled
PDF fixtures generated without downloading third-party worksheets.

#### Scenario: Corpus is generated twice
- **WHEN** the fixture generator runs twice from the same repository revision
- **THEN** it produces the same fixture inventory, expectations, and document bytes

#### Scenario: Corpus composition is inspected
- **WHEN** the generated corpus manifest is read
- **THEN** it contains both supported worksheets and deliberately ambiguous or unsupported worksheets

### Requirement: Supported fixtures exercise the existing contract
Supported fixtures SHALL cover realistic combinations of numbered and
command-style questions, wrapped prompts, answer lines and aligned line groups,
blank boxes, supported text fields, font and margin variation, modest
indentation, local vertical gaps, one and multiple pages, page-edge questions,
five through twenty questions, and textual or numeric single-region responses.

#### Scenario: Supported corpus is evaluated
- **WHEN** every fixture labeled supported is parsed through the production contract seam
- **THEN** every accepted question preserves the expected order and maps to exactly one approved local response area on the same page

### Requirement: Rejection fixtures exercise fail-closed behavior
Rejected fixtures SHALL include multiple choice, checkboxes, table entry,
answer keys, teacher guides, essay areas, remote or end-collected answers,
multi-column layouts, competing or unclaimed writable spaces, cross-page
associations, unsupported transforms, image-only scans, questionless pages,
and unmappable forms or diagrams.

#### Scenario: Unsupported corpus is evaluated
- **WHEN** every ambiguous or unsupported fixture is parsed through the production contract seam
- **THEN** no assignment is accepted and each result records one or more stable rejection reason codes

### Requirement: Evaluation reports agreement and unsafe acceptance
The evaluation report SHALL include document decision agreement,
supported-document acceptance, unsupported-document rejection, unsafe
acceptance count, question-count agreement, question-order agreement,
response-region detection agreement, question-to-response association
agreement, response-type agreement where applicable, and rejection counts by
reason code.

#### Scenario: Evaluation completes
- **WHEN** the complete fixture corpus is evaluated
- **THEN** the report contains every required metric and an unsafe acceptance count of zero

#### Scenario: A fixture result disagrees with its adjudicated expectation
- **WHEN** an expected supported fixture rejects or an expected rejected fixture is accepted
- **THEN** the report identifies that fixture and classifies the disagreement for individual review

### Requirement: Evaluation preserves approved terminology
Active contract reports and metric keys MUST use agreement, adjudication,
abstention, rejection, and unsafe-placement language and MUST NOT describe
AI-adjudicated silver labels as accuracy, correctness, ground truth, or human
gold.

#### Scenario: Active evaluation outputs are policy-checked
- **WHEN** evaluation source and generated reports are scanned by the terminology policy test
- **THEN** prohibited evaluation terminology is absent

### Requirement: Red-team evaluation cannot relax write authority
Decorative lines, choice numbering, multi-line response groups, overlapping
graphics, shifted question associations, misleading two-column order,
unclaimed spaces, and semantic attempts to promote unauthorized geometry SHALL
never become valid response destinations merely to increase supported-fixture
acceptance.

#### Scenario: Semantic output selects unauthorized geometry
- **WHEN** semantic output references geometry that deterministic extraction did not approve
- **THEN** the fixture is rejected and unsafe acceptance remains zero

#### Scenario: A supported fixture rejects
- **WHEN** investigation cannot prove that the document fits the existing contract
- **THEN** the fixture remains rejected rather than weakening geometry or write authorization
