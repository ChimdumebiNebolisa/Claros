## Why

Claros already has a real worksheet, session, confirmation, write, side-panel,
voice, restore, and export flow, but its public and product surfaces need a
first-principles redesign grounded in the current behavior rather than a new
mock experience. This experiment makes the product easier to understand and
more coherent at desktop and mobile while preserving the safety boundary that
keeps student-approved text, server authorization, and physical placement
separate.

## What Changes

- Reverse-engineer and freeze the current reachable product in redesign docs.
- Complete live visual reconnaissance across education, document, workflow,
  text-first editing, and workspace products.
- Generate original Claros UI references using the locked image-to-code visual
  authority before implementation.
- Redesign `/` around a calm, product-led explanation and real sample entry.
- Redesign `/app` across empty, processing, workspace, review, confirmed,
  written, side-panel, layout-review, error, export, and mobile states.
- Preserve existing upload/sample, task/target, typed, optional voice,
  confirmation, write-token, safe placement, persistence, export, keyboard,
  ARIA, live status, reduced-motion, and responsive behavior.
- Verify rendered desktop/mobile output and run behavioral, accessibility,
  security, adversarial, and final code-review gates.

## Capabilities

### New Capabilities

- `landing-and-workspace-redesign`: A coherent, image-first presentation for the
  public landing and worksheet workspace that exposes the existing product
  states and actions without changing their semantics.
- `behavior-preserving-worksheet-flow`: A documented and regression-verified
  preservation contract for entry, task/target selection, typed and voice
  interaction, confirmation, deterministic writing, side-panel fallback,
  restore, export, accessibility, and responsive operation.

### Modified Capabilities

None. No existing OpenSpec capability catalog was present at the baseline;
these are the first change-local specifications for the experiment.

## Impact

- Presentation: `frontend/landing.html`, landing build source/styles, and
  `frontend/app.html`/`styles/app.css` as needed.
- Stable client seams: `frontend/app.js`, `ui-state.js`,
  `worksheet-view.js`, and voice modules only where a presentation state cannot
  be expressed locally.
- Documentation: `docs/redesign/`, `docs/agents/engineering.md`, and the
  concise root guidance.
- Verification: existing Python/JS suites, local FastAPI browser workflows,
  rendered evidence under ignored `output/playwright/`, and OpenSpec artifacts.
- No backend API, production configuration, deployment, main branch, or
  third-party runtime asset changes are intended.
