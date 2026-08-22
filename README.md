# Claros

Claros is a focused completion workspace for students who need less typing. The
reconstructed V1 keeps a worksheet's original page visible, separates tutoring
from the final answer, requires explicit approval before commit, and exports a
new PDF only from committed answers.

## Local run

```bash
npm install
npm run build
npm test
node server/index.mjs
```

In another terminal, run `npm run dev` and open `http://localhost:5173`. The
sample worksheet is available from the landing page or
`/api/v1/demo.pdf`. The local API accepts that authored fixture and rejects
unknown PDFs with a stable validation error until an evidence-backed parser is
added.

The visual-state and browser checks are available with `npm run build-storybook`
and `npm run test:e2e`. The latter builds the app, serves the production bundle,
and runs the Playwright/axe smoke test.

The frontend uses React/Vite, Tailwind/Radix source primitives, XState, Zod,
React-PDF, resizable panels, dropzone, Storybook/MSW, and Playwright/axe. Each
library maps to a documented workflow, PDF, accessibility, or runtime-safety
boundary; no second state or design system is introduced.

## Product contract

The supplied reconstruction PRD is the product source of truth and the supplied
`CLAROS_DESIGN.md` is the visual source of truth. The active OpenSpec change is
`openspec/changes/claros-reconstruction/`.

The first slice deliberately excludes scans/OCR, multiple choice, tables,
drawings, teacher review, arbitrary geometry, and production persistence. These
are new contracts, not hidden fallbacks.

## Safety notes

- Session identifiers are HttpOnly cookies; no assignment secrets are stored in
  browser storage.
- Placement and commit are server-owned and bound to exact answer text.
- The original PDF is never mutated; export returns a derivative PDF.
- Voice is optional. If SpeechRecognition is unavailable, typed input remains
  complete.
