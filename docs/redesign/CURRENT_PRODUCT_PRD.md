# Current Product PRD: Claros

Status: behavior-freeze baseline for `experiment/claros-image-to-code-redesign`

Baseline source: `origin/main` at `63f8b0f611903f64dc5c4fa7b62390c83da5c452`

This document describes the reachable product as implemented at the baseline.
It is not the redesign brief and does not prescribe a visual system.

## Product summary

Claros is a human-free worksheet-understanding and tutoring workspace. A
student opens a structured PDF worksheet, selects one task at a time, reasons
with optional voice guidance or typed input, reviews the exact proposed answer,
confirms it, and then explicitly chooses whether to write it to a verified
response region or to the exported side panel when physical placement is not
safe.

The core product promise is: help the student think through a worksheet while
keeping the student in control of the exact answer and the physical destination.
Confirmation is deliberately not writing.

## Users and problem

Primary users are students who benefit from guided reasoning and a complete
typed path, including students with typing or speech constraints. Secondary
users are teachers, parents, and evaluators who need the resulting worksheet to
remain traceable and safe.

The problem is not simply “get an answer.” A worksheet may contain multiple
tasks, response areas, tables, choices, or uncertain geometry. Claros must help
the student understand the task without inventing source text or coordinates,
and must make the transition from draft to confirmed answer to written answer
legible.

## Supported use cases

- Open the public landing page and learn the product boundary.
- Open `/app` and choose an official sample worksheet.
- Upload a PDF up to the configured bounded size.
- Review parsed pages, tasks, structured choices, and response targets.
- Work by keyboard and typed text without microphone access.
- Optionally start a Gemini Live voice session when credentials and browser
  audio support are available.
- Draft, edit, review, confirm, and explicitly write answers task by task.
- Route uncertain or unsafe placement to a labeled export side panel.
- Resume a durable browser session when restore data remains valid.
- Export the original worksheet with deterministic answer stamping and any
  side-panel pages.

## Product surfaces

| Surface | Current responsibility |
| --- | --- |
| `/` | Public explanation, interactive non-writing proof, safety/accessibility story, FAQ, and entry CTA. |
| `/app` empty | PDF upload, official sample links, drop target, processing facts, typed-only notice. |
| `/app` processing/error | Progress stages, recoverable error, retry, and replace actions. |
| `/app` workspace | Document page/canvas, task navigation, response targets, typed answer editor, voice/session status, confirmation, writing, side-panel notice, and export. |
| `/api/*` | Assignment upload, session lifecycle, confirmation, write authorization, preview, restore, and export contracts. |

## Task and response-target model

The parser produces a document manifest with stable task IDs, source blocks,
task prompt text, choices where applicable, and zero or more response-region
links. A task can have multiple response targets such as an answer field and an
explanation field. Each target has a stable `response_region_id`, label, page
and geometry evidence owned by the server, safety status, and a side-panel
fallback when placement cannot be verified.

The browser may select a task and response target, but it must not provide
geometry to authorize a write. Client state is advisory; server-loaded
manifests and write validation are authoritative.

## Primary user journeys

### Landing

1. Load `/` with the skip link, primary navigation, hero, interactive proof,
   workflow explanation, safety/accessibility section, FAQ, and footer.
2. Choose “Open worksheet” or the canonical short-answer sample.
3. The proof composition is non-writing marketing UI; its buttons do not call
   the worksheet write API.

### Entry and processing

1. `/app` starts in `empty` with PDF file chooser, drop zone, and three official
   sample links.
2. A sample link fetches `/api/samples`, downloads the selected first-party PDF,
   and passes it through the same upload path as a user file.
3. Upload posts to `/upload?review_mode=direct`.
4. The UI exposes Uploading PDF, Reading pages, Finding student tasks,
   Checking answer locations, and Preparing worksheet.
5. A successful response applies the assignment manifest and enters `ready`,
   or `needs_layout_review` when the parser cannot safely promote geometry.
6. A failure enters `error`, keeps Retry and Replace PDF available, and does
   not claim that the worksheet was prepared.

### Workspace and typed answer

1. The workspace shows the original page preview, page controls, task list,
   task progress, response-target choices, and current placement status.
2. The student selects a task and target. The typed path is always present.
3. Typing updates only the draft for the selected task/target. Editing a
   previously confirmed draft clears the confirmation and requires review
   again.
4. “Review answer” or the equivalent transition shows the exact proposed text
   and a clear statement that it has not been written.
5. “Confirm answer” sends the exact task, target, and answer text to the server.
   The server returns a single-use write token for that exact confirmation.
6. A separate “Write confirmed answer” action uses the token and session
   credentials. Success marks the target written and clears the consumed token.

### Voice

Voice is an optional transport layered over the same task/answer states. The
browser requests microphone access only after the student starts voice. The
voice bridge can select tasks, surface proposed answers, announce confirmation
and write readiness, and request export, but it cannot bypass explicit
confirmation or server write authorization. If provider loading, credentials,
microphone access, or the live connection fails, Claros reveals a typed fallback
and leaves the core flow usable.

### Unsafe placement and layout review

If a response region is absent, unresolved, low-confidence, invalid, overflowed,
or otherwise unsafe, the document enters a layout-review or safe-side-panel
state. The UI must explain that the worksheet page remains unchanged and that a
confirmed answer can be included on the labeled export side panel. It must not
invent or silently repair coordinates.

### Persistence and export

The browser keeps a small session pointer in `sessionStorage` containing the
assignment/session identifiers, capability, and active task/target. The server
session is durable for the configured lifetime. On reload the client calls
restore and either reapplies response states or clears expired/invalid state
with a recoverable notice.

Export is a separate authorized POST. It requires at least one confirmed,
written answer, returns the original PDF with deterministic stamps and appended
side-panel pages where needed, and downloads a safe assignment-based filename.
The legacy query-string export path is disabled.

## Current state vocabulary

Workspace states: `empty`, `uploading`, `parsing`, `ready`,
`needs_layout_review`, `exporting`, `complete`, and `error`.

Voice states: `unavailable`, `idle`, `connecting`, `listening`, `speaking`,
`answer_detected`, `confirming`, `confirmed`, `writing`, `stopped`, and `error`.

Response stages: capture/draft, review/proposed, confirmed/not written,
writing, and written. Placement states distinguish verified physical regions,
side-panel fallback, and blocked/unresolved targets.

## Failure and loading behavior

- Uploads are bounded and concurrency/rate limited by the server.
- Parse or storage failure returns a recoverable error; the UI offers retry or
  replacement and retains no fake success state.
- Provider session configuration failure keeps typed work available.
- Expired assignment capability/session credentials require reload or a new
  upload; stale confirmation is not reused.
- A write conflict, invalid token, changed worksheet source, or authorization
  error resets the affected confirmation path and explains the next action.
- Export with no written answer is rejected as a recoverable product error.

## Accessibility and responsive requirements

The product has a skip link, semantic regions, labels, live status/alert areas,
visible focus styling, keyboard-operable controls, editable text fields, and a
reduced-motion preference. Microphone access is never required. At small widths
the app changes to a Worksheet/Answer switch rather than hiding either task.
Touch targets and long prompts/answers must remain usable without horizontal
clipping.

## Known baseline limitations

- A browser run from this worktree without configured GCS credentials reaches
  the real sample download and upload endpoint but ends in the existing
  recoverable 500 error because `GCS_BUCKET_NAME` is absent. This is an
  environment limitation, not a redesign behavior to mask.
- Gemini Live cannot be verified without provider credentials and microphone
  support; the typed-only and unavailable states are the local baseline.
- The isolated worktree initially lacks `node_modules`, so the frontend lint/
  typecheck suite requires the documented install step before it can run.

## Explicit redesign non-goals

- No backend rewrite, storage policy change, provider swap, production config,
  deployment, or merge to main.
- No new answer-generation behavior or relaxed confirmation rule.
- No removal of official sample/upload behavior, side-panel fallback, export,
  restore, typed operation, or accessibility semantics.
- No runtime dependency on third-party design assets or copied site code.

## Functional acceptance criteria

The redesign is acceptable only if it keeps the same API/state semantics and
the following remain true: a student can enter with a sample or upload; see
processing and recoverable failure; select tasks and targets; type and edit;
review exact text; confirm without writing; explicitly write only through the
server token path; see safe versus side-panel destination; restore partial
work; export written answers; use the keyboard without voice; and recover when
voice or provider services are unavailable.
