## 1. Repository foundation

- [x] 1.1 Replace the tracked branch content with a new Vite/React/TypeScript
  project shell while preserving `main` and ignored local secrets.
- [x] 1.2 Initialize OpenSpec Codex integration and record the selected,
  pinned specialist revisions in `.agents/specialists.lock.json`.
- [x] 1.3 Establish concise root guidance and detailed engineering guidance
  covering deep modules, integrity invariants, accessibility, and security.

## 2. Domain and API vertical slice

- [x] 2.1 Add Zod-backed worksheet, question, answer-region, placement-plan,
  committed-answer, assignment, and rejection-code contracts.
- [x] 2.2 Add deterministic placement classification with fit, continuation,
  and blocked outcomes and exact-text tests.
- [x] 2.3 Add the XState workspace graph with separate draft, review,
  committing, committed, exporting, unsupported, and complete states.
- [x] 2.4 Add the server-owned demo/source adapter, session cookie, upload gate,
  plan-token binding, idempotent commit behavior, and safe export response.
- [x] 2.5 Add focused domain and state-machine tests through stable interfaces.

## 3. Student and marketing surfaces

- [x] 3.1 Add the Claros token system, Inter font, border/radius rules, focus
  styles, reduced-motion handling, and responsive breakpoints from the design
  reference.
- [x] 3.2 Add the public landing page with the supplied product language,
  sample worksheet artifact, supported-contract explanation, and workspace CTA.
- [x] 3.3 Add the upload/unsupported states with stable copy, sample download,
  file drop, keyboard action, and fail-closed error handling.
- [x] 3.4 Add the workspace paper preview, one-question panel, final-answer
  editor, optional voice controls, tutoring separation, review placement row,
  commit, edit, next, completion, and export states.

## 4. Verification and handoff

- [x] 4.1 Run TypeScript/Vite production build.
- [x] 4.2 Run focused Vitest contract, placement, and state-machine suites.
- [x] 4.3 Exercise demo load, upload hash gate, plan, commit, and PDF export over
  the running HTTP server.
- [x] 4.4a Add Storybook state stories with the Storybook accessibility addon,
  MSW browser handlers, and the Playwright/axe test harness.
- [x] 4.4 Add browser-rendered desktop/mobile screenshots and accessibility
  automation before making production-quality claims.
- [ ] 4.5 Replace the authored sample-only extractor with evidence-backed native
  text worksheet parsing and add the declared first-party corpus.
- [ ] 4.6 Add durable storage, physical TTL cleanup, and live provider/voice
  verification before deployment.
