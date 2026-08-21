# Verification

This file points to current verification evidence. Local deterministic evidence
is not provider or production evidence.

## Worksheet contract evidence

The accepted document boundary is defined in
[`SUPPORTED_WORKSHEET_CONTRACT.md`](SUPPORTED_WORKSHEET_CONTRACT.md). The
deterministic first-party contract corpus and stable agreement report live in
`evaluation/worksheet_contract_v1`. They are local AI-adjudicated silver
evidence; they do not establish live-provider or universal PDF support.

### 2026-08-21 narrow-contract release evidence

- Mainline baseline: `7200b078a43fca581f9f3cd94fc59274bbd7372a`.
- Expanded corpus: 29 deterministic first-party PDFs; 10 supported and 19
  rejected expectations; all 29 decisions agree; unsafe acceptances and
  supported rejections are zero.
- Supported geometry: question count/order agree for all 10 supported PDFs;
  response detection, association, and response type agree for all 76 tasks.
- Canonical-v1: all primary agreement metrics are 1.0, mean response-region IoU
  is 0.917697, and false-positive task/writable-region counts are zero.
- Focused hardening: 100 tests passed.
- Python release gate: 441 passed, 1 live-provider test skipped, 83.98 percent
  coverage (72 percent required).
- Frontend release gate: `npm run ci:frontend` passed, including lockfile
  installs, client/SSR builds, prerender, lint, typecheck, JS contract tests,
  frontend validation, and the Gemini browser bundle build.
- Demo: `test_demo_hero_fixture.py` and `test_demo_hero_export.py` passed.
- Local Docker: not run because the Docker Desktop Linux daemon was unavailable;
  this is not container evidence. GitHub `main` protection requires the remote
  `Docker image build` context before merge.
- Live provider and production runtime behavior were not exercised by this
  local pass.

## Current frontend evidence

The current landing evidence record is:

`docs/evidence/LANDING_SHADCN_2026-07-30.md`

It records the Shadcn/Vite integration base, interactive product-state
behavior, desktop and mobile checks, dark mode, accessibility, Lighthouse
results, and local test results.

The current worksheet workspace evidence remains:

`docs/evidence/FRONTEND_SIMPLIFICATION_2026-07-29.md`

It records confirmation/write request separation, failed-write recovery, and
the real workspace browser checks that the marketing-only refinement does not
replace.

## Production status

The Shadcn landing refinement is deployed:

- implementation commit:
  `423f65ae1d577c75ae62d2682c744ba45d3b1483`;
- Cloud Run service and revision:
  `claros` / `claros-00062-l2n`, serving 100 percent of traffic;
- immutable image:
  `gcr.io/<GCP_PROJECT_ID>/claros:423f65ae1d577c75ae62d2682c744ba45d3b1483`,
  digest
  `sha256:1b491be91fa0e822c107375f5dc3883549ed2cd74794fa14911258269661756e`;
- deployment workflow:
  [GitHub Actions run 30516312521](https://github.com/ChimdumebiNebolisa/Claros/actions/runs/30516312521),
  completed successfully at `2026-07-30T05:24:34Z`;
- production URL verified:
  `https://claros-fnaobzrxeq-uc.a.run.app`;
- verifier:
  the tracked GitHub Actions deploy workflow plus the current Codex task;
- direct response evidence at `2026-07-30T05:25:13Z`:
  `/health`, `/`, `/app`, `/landing-app.js`, `/styles/landing.css`,
  `/fonts/geist-latin-wght-normal.woff2`, and `/favicon.png` each returned
  HTTP 200 with the expected content type; and
- content probes found the current hero and server-rendered Review state,
  found no stale raster workspace captures, retained the mobile view switch in
  `/app`, and did not find the removed visible Reject control.

The workflow's tests, production image build, deployment, and static smoke
checks all passed. A production browser run exercised Review to Confirmed to
Added to export with zero console errors or warnings. This evidence does not
establish live worksheet parsing, production storage access, voice provider
operation, write authorization, or export behavior; those require separate
credentialed functional verification.
