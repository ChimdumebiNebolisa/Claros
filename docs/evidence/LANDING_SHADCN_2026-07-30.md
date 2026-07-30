# Shadcn landing refinement evidence - 2026-07-30

## Scope and provenance

- Mainline base:
  `6f60f436b7462e970b3a28be9f4c7614529df2e5`.
- Starting tracked-diff identity:
  `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`.
- Release worktree:
  `codex/frontend-simplification-release`.
- Contributor evidence:
  current Codex task, repository diff, browser artifacts, and test output. No
  unavailable session ID or exclusive authorship is claimed.

The original dirty implementation workspace remains preserved. This change
starts from the clean deployed mainline release worktree.

## Design and implementation

- Shadcn CLI:
  `4.16.0`, initialized with the supported Vite template and Radix base.
- Owned Shadcn components:
  Button, Badge, Card, Tabs, Textarea, Separator, and Accordion.
- Runtime:
  React `19.2.6` with Vite `8.1.5`.
- Typeface:
  self-hosted Geist variable font.
- Theme:
  near-white and dark navy with one cobalt interaction accent, semantic green
  for written success, and matching system dark mode.
- Rendering:
  Vite creates deterministic landing assets and a server-rendered snapshot;
  the client hydrates only to provide the product-state interactions.
- Delivery:
  FastAPI serves the compiled entrypoint and applies standard gzip compression
  to static responses larger than 1,000 bytes.

The hero product surface is a real React component preview, not a raster
capture or a set of empty screenshot rectangles. It renders a meaningful
sample worksheet question beside working Capture, Review, Confirmed, and
export states. The marketing interaction is deliberately local and does not
call confirmation, write, assignment, storage, or provider APIs.

## Browser evidence

- Browser driver:
  pinned `@playwright/cli` `0.1.17`.
- Local server:
  `python scripts/run_demo.py`.
- Desktop viewport:
  `1440x900`.
- Mobile viewport:
  `390x844`.
- Ignored evidence directory:
  `output/playwright/landing-shadcn-20260730/`.

Observed behavior:

- the desktop hero fit inside the initial viewport with a two-line headline
  and visible primary action;
- the product preview started in Review, moved to Confirmed only after the
  explicit button, and moved to Added to export only after the separate
  destination action;
- the mobile layout used a single column, preserved the complete worksheet and
  answer example, and kept interactive targets at least 44px high;
- system dark mode preserved the same hierarchy and cobalt interaction role;
- the FAQ used keyboard-operable Shadcn accordion primitives;
- hydration completed without mismatch messages; and
- the final browser run reported zero console errors and zero warnings.

Captured evidence includes:

- `landing-desktop-final.png`
- `landing-mobile.png`
- `landing-mobile-dark.png`
- `landing-focus.png`

## Lighthouse

The final local mobile-throttled report recorded:

- Performance: 80
- Accessibility: 100
- Best Practices: 100
- SEO: 100
- First Contentful Paint: 1.6 seconds
- Largest Contentful Paint: 1.8 seconds
- Total Blocking Time: 790 milliseconds
- Cumulative Layout Shift: 0

The Lighthouse CLI wrote the complete JSON report, then returned a Windows
`EPERM` while removing its temporary Chrome profile. The scores above come
from the written report, not from an inferred successful process exit.

## Verification status

Completed locally:

- Shadcn/Vite build and server prerender
- ESLint
- TypeScript typecheck
- frontend static contract validation
- focused frontend/static/integration pytest
- Playwright desktop, mobile, interactive-state, dark-mode, and console checks
- `python -m ruff check .`
- full pytest: 418 passed, 1 skipped, 83.66 percent coverage
- `npm run ci:frontend`
- `git diff --check`

The root npm audit still reports five advisories in the existing dependency
tree: two moderate, two high, and one critical. The new isolated marketing
package reports zero advisories.

The local Docker build could not start because the Docker Desktop Linux engine
was unavailable. The tracked deployment workflow performed the authoritative
fresh production container build successfully.

## Production evidence

- implementation commit:
  `423f65ae1d577c75ae62d2682c744ba45d3b1483`;
- deployment workflow:
  [GitHub Actions run 30516312521](https://github.com/ChimdumebiNebolisa/Claros/actions/runs/30516312521),
  completed successfully at `2026-07-30T05:24:34Z`;
- Cloud Run service and revision:
  `claros` / `claros-00062-l2n`, serving 100 percent of traffic;
- immutable image:
  `gcr.io/<GCP_PROJECT_ID>/claros:423f65ae1d577c75ae62d2682c744ba45d3b1483`,
  digest
  `sha256:1b491be91fa0e822c107375f5dc3883549ed2cd74794fa14911258269661756e`;
- production URL:
  `https://claros-fnaobzrxeq-uc.a.run.app`; and
- direct response evidence at `2026-07-30T05:25:13Z`:
  `/health`, `/`, `/app`, `/landing-app.js`, `/styles/landing.css`,
  `/fonts/geist-latin-wght-normal.woff2`, and `/favicon.png` each returned
  HTTP 200 with the expected content type.

The production landing contained the current hero, server-rendered Review
state, and hydration entrypoint, and contained no stale workspace capture
reference. The production app retained the Worksheet and Answer mobile switch
and omitted the removed visible Reject control. A Playwright production run
moved the marketing example from Review to Confirmed and then Added to export,
with zero console errors and zero warnings. The landing bundle returned
`content-encoding: gzip` when requested with gzip support.

## Limits

This landing interaction is a truthful presentation of product states, not a
production worksheet session. It does not establish live Gemini behavior,
production storage access, voice-provider behavior, or production
write/export behavior. Those boundaries remain covered by the existing
workspace evidence and require separate credentialed verification.
