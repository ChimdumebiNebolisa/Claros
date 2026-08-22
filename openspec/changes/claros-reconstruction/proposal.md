## Why

Claros needs a clean product boundary around one safe workflow: a student
uploads a supported short-answer worksheet, works through one question at a
time, explicitly approves an exact final answer, and exports a new PDF. The
historical branch mixed multiple product generations and trusted too much
client-side coordination, so this branch rebuilds the V1 around the supplied
reconstruction PRD and canonical design reference.

## What Changes

- **BREAKING** Replace the historical runtime with a React + TypeScript Vite
  application and a small typed backend facade.
- Add whole-document upload validation with stable unsupported reason codes.
- Add the canonical upload, analysis, drafting, review, placement, commit,
  resume, completion, and export states.
- Add exact-answer integrity checks and task-bound commit authorization.
- Keep voice optional and subordinate to typed input; voice cannot commit,
  export, or control geometry.
- Add the light-first Claros design system, responsive workspace, accessible
  keyboard flow, and truthful state copy from the supplied design reference.
- Remove legacy target picking, layout review, broad OCR, teacher review, fake
  processing progress, and pre-export write semantics from the V1 runtime.
- Add focused domain, API, component, and end-to-end verification surfaces.

## Capabilities

### New Capabilities

- `worksheet-contract`: Validate the supported native-text short-answer PDF
  contract and return stable rejection reasons.
- `answer-integrity`: Model draft, review, placement, committed answer, and
  task-bound write authorization with exact-text preservation.
- `student-workspace`: Provide the responsive upload-to-export workflow,
  accessible state presentation, optional voice assistance, and session resume.
- `safe-export`: Revalidate source and placement, then export a new PDF from
  committed answers only.

### Modified Capabilities

None. The branch is rebuilt from an empty tracked content set.

## Impact

- New Vite/React/TypeScript frontend under `src/` and a small Node HTTP API
  adapter under `server/`.
- New runtime contracts and tests under `tests/`.
- New OpenSpec project integration and reconstruction artifacts.
- New dependency set for React Router, XState, Zod, PDF rendering, upload,
  accessible primitives, and verification tooling.
- Existing `main` and all other worktrees remain unchanged.
