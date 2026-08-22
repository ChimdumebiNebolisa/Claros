# Claros engineering guidance

## Product boundary

The reconstructed V1 is a human-free worksheet-understanding and tutoring
workspace for native-text, short-answer PDFs. Every accepted question has one
deterministic writable region directly below it on the same page. Unsupported
layouts are rejected during upload.

## Modules and seams

- `src/domain` owns typed product states, answer integrity, placement results,
  and transition guards. It does not render UI or call vendors.
- `src/domain/workspace-machine.ts` owns the XState workspace graph; `src/ui`
  coordinates the current assignment/session through small adapter calls.
- `src/adapters` owns HTTP, PDF rendering, voice transport, and browser-facing
  integrations. Vendor-specific behavior stays behind these seams.
- `src/ui` owns accessible React presentation. It consumes domain snapshots and
  dispatches typed events; it does not invent trusted coordinates or commit
  answers directly.

## Invariants

- A final answer is exact text and remains editable until explicit student
  confirmation.
- Review and commit are separate states and requests. Only a server-issued,
  task-bound placement plan may authorize commit.
- Geometry comes only from supplied physical evidence. Missing, ambiguous, or
  unsafe regions reject the upload; continuation pages are disclosed before
  commit and never silently rerouted.
- The source PDF is immutable. Export creates a new file from committed answers
  after source and placement revalidation.
- Session secrets and assignment authorization do not live in browser storage.
- User text and model output are rendered as text, not executable markup.

## Verification

Test observable behavior through stable interfaces: domain transition tests,
placement and exact-text tests, API contract tests, Storybook state stories,
component tests for keyboard and accessible states, and Playwright/axe checks
for the supported browser flow. Run the narrowest check after each slice and the
full applicable suite before handoff.

## Documentation and change hygiene

Update OpenSpec, README, environment examples, and API/schema docs with durable
behavior changes. Keep secrets in local environment files and never commit
private worksheets, raw provider payloads, or generated corpus output.

## Visual authority

`docs/CLAROS_DESIGN.md` is the controlling visual reference. `frontend-design`
provides the project-wide baseline; Impeccable is the primary authority for the
operational workspace and a bounded accessibility/state diagnostic for other
surfaces. The marketing route remains frontend-design-primary because the
reference already settles its composition and palette.
