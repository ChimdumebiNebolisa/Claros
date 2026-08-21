## Purpose

Give Claros a coherent, accessible visual presentation for public discovery
and real worksheet work while making every existing product state and action
easy to find without changing its semantics.

## ADDED Requirements

### Requirement: Public entry explains the product boundary

The public landing page SHALL present the student job, optional voice, typed
fallback, exact-answer review, explicit writing, safe placement, and side-panel
fallback before or alongside the real worksheet entry actions.

#### Scenario: Student starts from the landing page

- **WHEN** a user opens `/` and chooses the primary worksheet action
- **THEN** the user reaches the real `/app` flow and is not routed to a static
  demo-only worksheet

#### Scenario: Marketing proof is inspected

- **WHEN** a user interacts with the landing-page proof controls
- **THEN** the proof may change its illustrative state but never uploads,
  confirms, writes, or exports a real assignment

### Requirement: Worksheet states remain visually legible

The worksheet surface SHALL present entry, processing, ready, layout-review,
draft, review, confirmed-not-written, writing, written, error, and export
states with distinct status, task/target context, and next actions.

#### Scenario: Answer is confirmed but not written

- **WHEN** the server confirms an exact answer
- **THEN** the workspace shows the exact text, task/target context, destination,
  and a separate write action while stating that the page is not yet written

#### Scenario: Placement is unsafe

- **WHEN** the manifest marks a target unresolved or unsafe
- **THEN** the workspace explains the side-panel or layout-review destination
  and does not present guessed physical coordinates as safe

### Requirement: Responsive presentation preserves the complete flow

The product SHALL retain document access, task navigation, typed editing,
confirmation, writing, export, keyboard operation, and status communication at
desktop, small-laptop, and mobile widths.

#### Scenario: Student works at mobile width

- **WHEN** the viewport is narrow enough for the mobile treatment
- **THEN** the student can switch between Worksheet and Answer views and reach
  every required action without horizontal clipping

#### Scenario: User prefers reduced motion

- **WHEN** `prefers-reduced-motion: reduce` is active
- **THEN** nonessential transitions are reduced or removed while state changes,
  focus, and status remain understandable
