# Claros Surface Map

This map identifies what each surface must make understandable and actionable.
It intentionally describes information and behavior, not styling.

## Public / brand surface: `/`

### Landing shell

- Purpose: establish Claros as a guided, student-controlled worksheet product.
- User job: decide whether to open a worksheet and understand the safety
  boundary before uploading anything.
- Required information: product promise, typed fallback, optional voice,
  confirmation-versus-writing distinction, and safe placement/side panel.
- Required actions: skip to main content, navigate to explanation/safety/FAQ,
  open `/app`, and start the canonical sample.
- Important states: normal load, keyboard focus, reduced motion, small screen,
  interactive proof state changes that never call product APIs.
- Cannot be lost: “You decide” and “confirmation does not write.”

### Hero and sample entry

- Purpose: turn product understanding into a low-friction first action.
- User job: see the product in context and choose a real worksheet entry.
- Required information: real worksheet/task composition, “try the sample,” and
  the distinction between illustration and real workspace.
- Required actions: open sample and open worksheet.
- Important states: normal, focused CTA, reduced-motion/static proof.
- Cannot be lost: the CTA must reach the real `/app` flow, not a mock.

### Product explanation / workflow

- Purpose: explain capture, exact review, and destination choice as one chain.
- User job: understand why Claros pauses before writing.
- Required information: capture/reasoning, review exact words, destination.
- Required actions: none beyond reading and anchor navigation.
- Important states: responsive reflow and readable long copy.
- Cannot be lost: the three-step safety sequence.

### Proof / trust

- Purpose: demonstrate the separate answer states without touching a worksheet.
- User job: preview what “confirmed, not written” means.
- Required information: exact proposed text, unchanged worksheet, destination
  waiting for choice, and meaningful state labels.
- Required actions: presentation-only edit/change/add-to-export controls may
  update the proof; they must not write or export real answers.
- Important states: capture, review, confirmed, written illustration.
- Cannot be lost: proof copy must not imply that the marketing demo changes a
  real PDF.

### Safety, accessibility, FAQ, footer

- Purpose: answer trust and access questions before entry.
- User job: learn about placement evidence, typing, mic optionality, storage,
  and supported PDF shape.
- Required actions: FAQ disclosure, anchor navigation, worksheet CTA.
- Cannot be lost: no answer-vending framing, no voice requirement, and no
  hidden accessibility commitment.

## Product surface: `/app`

### Shared app shell

- Purpose: provide a stable context while setup and workspace states change.
- User job: know where they are, return home, get help, and understand status.
- Required information: Claros identity, assignment title when loaded, status,
  skip link, help/status notice, and export/replace actions when applicable.
- Important states: empty, processing, ready, layout review, exporting,
  complete, error.
- Cannot be lost: state transitions must not erase the current task or suggest
  that an answer was written when it was not.

### Upload / sample entry

- Purpose: get a real PDF into the parser.
- User job: choose a PDF or official sample and understand supported inputs.
- Required information: file constraints, sample descriptions, drop affordance,
  review/write/side-panel facts, and typed-only availability.
- Required actions: choose PDF, drop PDF, select a sample, retry, replace.
- Important states: idle, drag-over, uploading, parsing, error.
- Cannot be lost: every entry uses the real upload path.

### Document canvas

- Purpose: keep the original worksheet visible as physical evidence.
- User job: read the page, see the current answer region/overlay, and orient in
  a multi-page document.
- Required information: page image, page number/count, task/target marker,
  zoom, fit width, previous/next.
- Required actions: page navigation, zoom, fit width, target selection when a
  target is selectable through the view.
- Important states: page loading, preview error, safe overlay, side-panel
  fallback, layout review, mobile Worksheet view.
- Cannot be lost: no invented geometry and no replacement of the original page.

### Task navigation and progress

- Purpose: make one-task-at-a-time work predictable.
- User job: choose a task, see what is complete, and switch without losing
  state.
- Required information: task number/label, prompt, choices, response progress,
  active state, and assignment progress.
- Required actions: select task, select structured choice, switch target.
- Important states: active, draft, confirmed, written, blocked/layout review.
- Cannot be lost: task binding and per-target state isolation.

### Answer editor and session controls

- Purpose: give the student a complete typed interaction with optional voice.
- User job: draft/edit an answer, hear or read guidance, and know whether voice
  is listening/responding.
- Required information: task/target context, editor label, draft, transcript or
  status, mic availability, interrupt, type-instead, and fallback notice.
- Required actions: type, clear/edit, start/stop voice, interrupt, type instead.
- Important states: idle, listening, speaking, answer detected, unavailable,
  provider error, typed-only.
- Cannot be lost: microphone is optional and voice cannot write by itself.

### Review / confirmation / write

- Purpose: make exact answer ownership and authorization legible.
- User job: inspect exact text, confirm it, then choose the separate write.
- Required information: exact answer, task and response-target labels, current
  placement, unchanged-page statement, confirmation status, write status, and
  next action.
- Required actions: review/edit, confirm, change answer, reauthorize if the
  server allows it, write confirmed answer.
- Important states: draft, review, confirmed-not-written, writing, written,
  failed/conflict.
- Cannot be lost: confirm and write are different actions and requests.

### Unsafe placement / layout review

- Purpose: preserve safety when geometry cannot support a physical write.
- User job: understand why the page is not being changed and what export will
  contain.
- Required information: reason code/copy, safe side-panel destination, page
  unchanged, and any blocked action.
- Required actions: choose or keep side-panel target, retry/review if provided,
  continue with typed work.
- Important states: unresolved target, low confidence, overflow, source-change
  conflict, layout review required.
- Cannot be lost: uncertainty must be visible and must never be presented as a
  verified line.

### Export and completion

- Purpose: finish with a durable worksheet artifact.
- User job: know whether anything is written, export when eligible, and recover
  from a partial or failed export.
- Required information: written-answer count, side-panel count, original pages
  preserved, export status, download action, and error.
- Required actions: export, continue working, replace/restart when complete.
- Important states: disabled/no written answers, exporting, success/complete,
  export failure.
- Cannot be lost: export is authorized, deterministic, and based on written
  answers only.

## Responsive cross-surface rules

- Desktop can show document and answer/task context together.
- Small laptop must retain both the document and the answer controls without
  clipping or making the write action ambiguous.
- Mobile exposes a clear Worksheet/Answer switch and keeps upload, task
  selection, editor, confirmation, write, and export reachable.
- Every state retains a keyboard path, visible focus, readable status, and a
  reduced-motion alternative.
