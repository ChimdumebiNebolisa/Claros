## Purpose

Ensures every worksheet advertised as an official product sample satisfies the
active sequential short-answer worksheet contract.

## ADDED Requirements

### Requirement: Production exposes only supported samples
The product sample catalog and worksheet application SHALL expose only
`canonical-short-answer-ecosystems` as an official sample while it is the only
first-party fixture accepted by the active worksheet contract.

#### Scenario: Product catalog is requested
- **WHEN** a client requests the production sample catalog
- **THEN** the response contains `canonical-short-answer-ecosystems` and no unsupported fixture IDs

#### Scenario: Official samples are rendered in the application
- **WHEN** the worksheet application renders its official sample choices
- **THEN** it shows only the supported short-answer sample and does not show multiple-choice or multi-region math choices

### Requirement: Sample defaults and deep links remain contract-safe
Every production default sample and official-sample deep link SHALL resolve to
a worksheet that the active production parser accepts under the unchanged
contract.

#### Scenario: Default sample is opened
- **WHEN** a user opens the application sample shortcut without choosing an explicit fixture
- **THEN** the application selects `canonical-short-answer-ecosystems`

### Requirement: Rejection fixtures remain outside the product catalog
First-party multiple-choice, multi-region math, and other rejection fixtures
MUST remain available to tests and evaluation without being advertised through
the production sample catalog or user-facing official-sample controls.

#### Scenario: Evaluation loads an unsupported fixture
- **WHEN** the contract evaluator loads a repository-controlled rejection fixture
- **THEN** the fixture remains accessible to evaluation while absent from the production sample response and UI
