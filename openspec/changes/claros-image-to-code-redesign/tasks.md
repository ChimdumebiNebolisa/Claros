## 1. Baseline and planning

- [x] 1.1 Keep the experiment isolated from the dirty source worktree, record the baseline SHA and specialist routing, and verify `git status --short --branch` shows the dedicated branch without unrelated files.
- [x] 1.2 Complete the current-product PRD, behavior contract, surface map, and reference matrix from implementation, tests, and local browser evidence; verify all four docs exist and mention the documented credential limitation.
- [x] 1.3 Validate the OpenSpec artifacts with `openspec validate claros-image-to-code-redesign --strict` and verify the proposal/spec/design/tasks dependency chain is complete.

## 2. Visual references and foundation

- [x] 2.1 Capture the selected live reference pages at readable desktop/mobile sizes under ignored `output/playwright/` and verify the matrix paths exist.
- [x] 2.2 Generate dedicated original Claros references for landing hero/proof, upload entry, desktop workspace, confirmation/safety state, and mobile workspace using the locked image-to-code authority; verify each asset is saved under the experiment evidence path.
- [x] 2.3 Analyze the generated references and write `docs/redesign/VISUAL_SYSTEM.md`; verify it defines type, tokens, layout, semantic states, document/answer treatment, responsive behavior, motion, and anti-copy constraints.
- [x] 2.4 Implement one shared token/foundation layer without introducing a runtime third-party asset dependency; verify existing frontend contract selectors and `prefers-reduced-motion` hooks remain present.

## 3. Landing vertical slice

- [x] 3.1 Redesign the landing shell, hero, navigation, and primary entry composition against the generated reference; verify `/` loads, skip/navigation/CTA links work, and `npm run validate:frontend` passes.
- [x] 3.2 Redesign landing workflow, proof, safety/accessibility, FAQ, and footer sections while keeping proof controls presentation-only; verify no proof action calls upload, confirmation, write, or export APIs.
- [x] 3.3 Render landing at desktop, small-laptop, and mobile sizes and compare against the generated references; verify no overflow, unreadable copy, or missing keyboard focus is introduced.

## 4. Workspace vertical slice

- [x] 4.1 Redesign the `/app` empty, upload, sample, processing, and error composition around the existing DOM/API seams; verify empty state, real sample request, and missing-GCS recoverable error remain observable.
- [x] 4.2 Redesign the desktop workspace canvas, task navigation, response-target controls, progress, and page tools; verify task/target switching remains isolated and document preview controls still function.
- [x] 4.3 Redesign typed draft, review, confirmed-not-written, writing, written, voice-unavailable, and side-panel/layout-review states; verify the existing focused frontend state tests and confirmation/write API tests remain green.
- [x] 4.4 Redesign export/completion and recovery presentation; verify export stays separate, requires written answers, preserves the original-page copy, and reports failure honestly.
- [x] 4.5 Add the responsive Worksheet/Answer treatment for narrow screens; verify mobile upload, task selection, typed edit, confirmation, writing, and export remain reachable with keyboard and pointer.

## 5. Verification and review

- [x] 5.1 Install frontend dependencies and run the focused JS suites plus `npm run validate:frontend`; verify lint, typecheck, state, voice-bridge, worksheet-security, worksheet-targets, and contract checks pass.
- [x] 5.2 Run focused backend contract, sample-flow, write-invariant, persistence, export, and PDF tests; verify no answer-integrity or side-panel regression.
- [x] 5.3 Exercise the locally available browser red-team scenarios for entry, sample/error recovery, keyboard focus, FAQ/preview controls, reduced-motion styling, and responsive widths; use the existing state/API suites for loaded workspace transitions, and save screenshots/snapshots. The live sample workspace remains blocked by unavailable local storage/provider credentials.
- [x] 5.4 Run the Vibe Security review for touched DOM/API/document boundaries and adjudicate findings; verify no accepted Critical/High issue remains and no secret/raw worksheet content was introduced into logs or assets.
- [x] 5.5 Run Code Review Expert on the complete diff, fix accepted P0/P1 and concrete P2 findings, and rerender affected UI; verify review disposition is recorded in the final report.
- [x] 5.6 Run `python -m ruff check .`, relevant pytest coverage, `npm run ci:frontend`, `docker build -t claros:final .`, and `git diff --check` where dependencies permit; verify all limitations are explicitly reported. Docker was unavailable because the local Linux engine pipe was not running.
- [x] 5.7 Synchronize OpenSpec task status and redesign docs, perform the final writing-for-agents pass, and verify the branch is ready for human review with main untouched and nothing deployed.
