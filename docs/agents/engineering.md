# Claros engineering guidance

## Product boundary

Claros is a human-free worksheet-understanding and tutoring system. The browser
uses deterministic physical evidence from structured PDFs, optional Gemini Live
voice, and a complete typed path. Deterministic code owns geometry, validation,
student confirmation, write-token issuance, authorization, overflow handling,
and PDF changes. Models may propose tutoring actions or select from supplied
evidence; they do not invent source text, response targets, or coordinates.

The active redesign is a brownfield experiment. `docs/redesign/BEHAVIOR_CONTRACT.md`
is the preservation oracle; a visual change is incomplete until the affected
contract scenarios still hold.

## Modules and seams

- `main.py` owns HTTP transport and request validation; service modules own
  assignment lifecycle, sessions, writing, export, storage, and document
  processing. Keep transport details out of business rules.
- `frontend/app.js` owns the existing worksheet workflow orchestration;
  `frontend/ui-state.js`, `frontend/session-rules.js`, and
  `frontend/worksheet-view.js` are the stable seams for state transitions,
  answer readiness, and document rendering. Prefer local presentation changes
  over duplicating state or rewriting these contracts.
- `frontend/voice-product-bridge.js` and
  `frontend/voice-live-transport.js` isolate optional voice transport. Voice
  failure must leave the typed interface complete and usable.
- Create a new module or adapter only for a current variation or external
  integration seam. One implementation is not evidence for a hypothetical
  abstraction; avoid pass-through layers.

## Non-negotiable invariants

- An answer is task-bound and may be written only after the student explicitly
  confirms that exact answer for that task.
- Confirming an answer and writing it are separate states and requests.
- Geometry comes only from supplied physical evidence. Unsafe, missing,
  unresolved, or overflowing regions route to the labeled side panel.
- Original worksheet pages remain the export source. The UI never silently
  guesses placement or truncates confirmed text.
- Microphone access is optional. Keyboard, pointer, typed input, focus, live
  status, and reduced-motion paths remain complete.

## Verification

Test observable behavior through stable interfaces and real seams. Use focused
unit tests for pure state or validation rules, vertical-slice tests for core
assignment/write/export flows, and browser checks for entry, task switching,
typed confirmation, safe/unsafe placement, export, refresh/restore, keyboard,
and responsive states. Add a regression test for each confirmed defect.

For user-facing changes, render `/` and `/app` at desktop, small-laptop, and
mobile sizes. Compare implementation screenshots to the generated references
and to the behavior contract; do not treat a polished screenshot as evidence
that backend behavior works.

## Security and privacy

Keep secrets in environment configuration and document variable names without
values. Do not log worksheet contents, raw provider payloads, session secrets,
or private PDFs. Treat uploaded/parser/model-controlled text as untrusted and
preserve safe DOM insertion. Keep authorization and write-token checks on the
server; client state is advisory.

## Documentation and change hygiene

Update the canonical product, behavior, architecture, configuration, or test
documentation in the same change when durable behavior changes. Keep the root
`AGENTS.md` concise and use OpenSpec for the active redesign plan. Preserve
unrelated work, avoid production configuration changes, and keep generated
screenshots/references under the documented redesign evidence paths rather than
introducing runtime dependencies on external assets.
