# Claros Behavior Contract

This is the hard preservation oracle for the redesign. Visual changes may
reorganize presentation, but an affected scenario is not complete until its
observable behavior remains true.

## 1. Entry and assignment preparation

| Scenario | Required behavior |
| --- | --- |
| Landing load | `/` renders without requiring a session, exposes skip/navigation/CTA links, and keeps its interactive proof non-writing. |
| Open worksheet | `/app` begins in the empty state with PDF chooser, drop target, official sample choices, and typed-only availability. |
| Sample choice | A canonical sample is fetched from `/api/samples` and `/samples/{id}.pdf`, then uses the normal `/upload?review_mode=direct` path. No demo-only success state is allowed. |
| Upload | The client posts the selected PDF and waits through real upload/parse states. It does not fabricate an assignment, task, response target, or coordinate. |
| Processing | The user can see Uploading PDF, Reading pages, Finding student tasks, Checking answer locations, and Preparing worksheet. |
| Successful parse | The returned assignment ID, title, parse status, page count, document, tasks, and response target map become the workspace source of truth. |
| Layout review | `needs_layout_review` remains explicit. Unresolved geometry does not become a writable physical target. |
| Failure | Parse, upload, capability, or storage failure enters an honest recoverable error with Retry/Replace where supported. No success copy or silent retry replaces it. |

## 2. Workspace

The redesign must preserve these visible and interactive capabilities:

- Show original page previews, page count, current page, fit-width, zoom, and
  previous/next controls.
- Keep the document view and answer/task view reachable at desktop and mobile.
- Present the active assignment title and current workspace status.
- List tasks in stable order with labels, progress, and active selection.
- Keep structured choices and their task binding when present.
- Present every response target supplied by the manifest, including target
  labels, active target, target progress, and placement status.
- Keep response target switching independent from task switching; switching
  must not copy text or confirmation from another target.
- Keep draft, review, confirmed, writing, and written states distinguishable.
- Preserve notices, live status, alerts, transcript/status controls, and
  failure recovery actions.

## 3. Answer integrity

These invariants are non-negotiable:

1. An answer belongs to one exact `task_id` and `response_region_id`.
2. The client never invents prompt text, choice text, source-block IDs,
   response-region IDs, or PDF coordinates.
3. A draft is not a confirmed answer.
4. Confirming does not write to the worksheet.
5. The server receives the exact answer text the student approved and binds it
   to the selected task and response target.
6. Confirmation returns a server-issued, single-use write token scoped to that
   session/task/target/answer.
7. Writing requires the matching session credentials and token; client state
   alone cannot authorize it.
8. The write request uses the approved exact answer. It does not regenerate,
   summarize, truncate, substitute, or re-ask the model for text.
9. A consumed token cannot write again; changed answer text or target requires
   a new review and confirmation.
10. An unsafe, missing, invalid, unresolved, or overflowing physical region is
    never promoted by the client into a safe coordinate write.
11. Safe physical writes and labeled side-panel writes remain distinguishable
    in the UI and export.
12. Original worksheet pages are preserved as the export source.

## 4. Typed interaction

- The typed editor is available without voice, credentials, or microphone.
- A user can focus, type, edit, clear, and submit the current draft with the
  keyboard and pointer.
- Editing a confirmed response invalidates the old confirmation/token and
  returns the response to review/capture as currently implemented.
- Task and target changes preserve their own drafts/states and do not leak
  text across targets.
- Long answers remain editable and are never silently clipped by the redesign.

## 5. Voice interaction

- Microphone access is requested only after the user starts a voice session.
- The voice bridge may select a task, propose an answer, announce readiness,
  and request export, but it cannot authorize a write.
- Listening, speaking, answer-detected, confirming, writing, stopped, and error
  states remain visible in the same state machine.
- Interrupt remains available while the provider is speaking when supported.
- Provider import, connection, permission, quota, and transcript failures
  reveal or retain the typed fallback.
- No screen may imply that voice is required for a complete answer flow.

## 6. Confirmation and writing

The preserved sequence is:

```text
draft -> review exact text -> explicit confirm -> confirmed/not written
     -> explicit write action -> writing -> written
```

The UI must not combine Confirm and Write into one ambiguous action. In the
confirmed state it must show the exact approved text, the task/target context,
the destination (verified region or side panel), and the next write action or a
clear blocked reason. On write success it shows the answer as written and
removes the token from usable client state.

## 7. Placement and side panel

- Physical placement is based on deterministic server evidence and manifest
  validation, not browser-supplied geometry.
- `side_panel_fallback` is a safe destination, not an error to hide.
- Layout review can block a physical write while still allowing the student to
  preserve the confirmed answer for an export side panel when the server
  permits it.
- Side-panel copy includes enough task label/prompt context to be useful and
  does not overwrite the original page.
- Overflow is handled deterministically; confirmed text is not silently
  truncated to fit a physical region.

## 8. Persistence and restore

- The browser stores only the current session pointer needed for restore, not
  secrets or raw worksheet content beyond the existing contract.
- Reload calls the restore endpoint with session credentials when present.
- Valid response states, drafts, active task, and active target return to the
  workspace.
- Expired, invalid, mismatched, or source-changed state is cleared or demoted
  with an actionable notice. A stale confirmation is never treated as valid.

## 9. Export

- Export is a separate user action and authorized POST.
- The client does not use query-string answers or inject answer text into an
  export URL.
- Export requires written answers under the current session; zero-answer
  export remains a recoverable rejection.
- The server loads the canonical original PDF/manifest and deterministically
  stamps safe regions or appends the side panel.
- Export keeps the original pages and returns a safe filename.

## 10. API contracts consumed by the frontend

The redesign should preserve request/response meaning and names for:

- `GET /api/samples`
- `GET /samples/{sample_id}.pdf`
- `POST /upload?review_mode=direct`
- `GET /api/session-config/{assignment_id}`
- `POST /api/session/start`
- `POST /api/session/{session_id}/confirm`
- `POST /api/session/{session_id}/restore`
- `POST /api/session/{session_id}/reauthorize-write`
- `POST /api/write/{assignment_id}`
- `GET /api/assignments/{assignment_id}/pages/{page_number}.png`
- `POST /export/{assignment_id}`
- `DELETE /api/assignments/{assignment_id}`

The client may add presentation-only adapters at existing seams, but must not
change backend semantics to make a visual state easier to render.

## 11. Accessibility contract

- Skip links, semantic landmarks, accessible names, labels, live status, and
  alert semantics remain present and truthful.
- All controls are keyboard operable in logical order with visible focus.
- Editable fields are visibly editable and associated with their task/target.
- Focus is not trapped in a decorative panel or lost after state updates.
- Contrast remains readable for body, controls, status, warnings, and focus.
- `prefers-reduced-motion` disables nonessential transitions and does not remove
  information.
- Mobile Worksheet/Answer switching keeps both document and response actions
  reachable.

## 12. Red-team scenarios

Before completion, run these against the redesigned UI and compare with the
baseline implementation:

- sample/upload success and missing-GCS failure;
- task switching with two response targets;
- changing a draft after confirmation;
- attempting write before confirmation;
- stale/reused/mismatched write token;
- safe target versus side-panel target;
- unresolved layout review;
- refresh after partial completion;
- export before and after a written answer;
- voice unavailable and typed-only flow;
- keyboard-only entry, confirmation, write, and mobile switching;
- long prompt/answer and narrow viewport.
