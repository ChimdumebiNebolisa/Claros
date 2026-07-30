# Frontend simplification evidence — 2026-07-29

## Scope and provenance

- Original implementation workspace baseline: `e97192f51a9c3d94b8a0350e0bde0589a29621ca`.
- Original workspace checkpoint diff identity: `f6d89466`.
- Clean mainline integration base:
  `c87d8a5bcbd0b955652d8ecc38a843233a615480`.
- Visual release diff identity before this evidence annotation:
  `4c30a6c78e370639cd33695f37f876d17b156b02`.
- Release worktree: `codex/frontend-simplification-release`.
- Contributor evidence: current Codex task, repository diff, test output, and
  browser artifacts. No unavailable session ID or exclusive authorship is
  claimed.

The dirty implementation workspace was preserved. The release was ported onto
current `origin/main` so the newer canonical-task, multi-response-target,
voice-transport, authorization, and lifecycle changes were not replaced by an
older tree.

## Product-state capture protocol

- Browser driver: pinned `@playwright/cli` `0.1.17`.
- Server: `python scripts/run_demo.py`.
- Storage: task-owned local directory under
  `output/playwright/frontend-release/c87d8a5-b16a7e6f-20260729/`.
- Fixture: repository-owned synthetic `demo/hero_worksheet.pdf`.
- Answer:
  `Clear water has more insects, so it offers fish more food.`
- Desktop viewport: `1440x900`.
- Mobile viewport: `390x844`.

Tracked landing assets were captured from the running application without DOM
injection, compositing, retouching, or fabricated browser chrome:

| Asset | State | Dimensions | SHA-256 |
| --- | --- | ---: | --- |
| `frontend/sample-workspace-review.png` | Review, desktop workspace bounds | 1242x671 | `ED10E7339A982A0FFCB0187EFECE9E5BEBCBF1B32C1079382CAB621135DD8DDF` |
| `frontend/sample-workspace-review-mobile.png` | Review, explicit Answer view | 390x844 | `8F6D5DF5806024D7C528F1C46E1FBEBA7360D62DD4DA53A373221CF9699C7619` |
| `frontend/sample-workspace.png` | Confirmed, not written, desktop workspace bounds | 1400x815 | `615DA08764C7DB1789A1D14C812CF6A6E20705BB6589230B0AD2EF086D35064A` |
| `frontend/sample-workspace-mobile.png` | Confirmed, not written, explicit Answer view | 390x844 | `C2B10BDE796A507D8EF879EE16E955213179AA6F6FCA10EF83E2579246A2495F` |

Ignored browser evidence includes:

- `review-desktop-full.png`
- `failed-write-desktop.png`
- `written-desktop.png`
- `landing-1440x900.png`
- `landing-390x844.png`

## Observed behavior

- Desktop rendered the worksheet and answer panel together at an approximately
  two-thirds / one-third proportion.
- At 390px, a newly loaded assignment opened on Worksheet.
- Resizing from desktop to mobile did not change the explicit view.
- Selecting Answer changed only the mobile presentation; the draft and active
  task remained mounted.
- Review hid the draft editor and exposed only Edit answer and Confirm answer.
- The request list after confirmation contained
  `POST /api/session/<session>/confirm` with HTTP 200 and no `/api/write/`.
- Confirmed showed the fixed exact answer, Change answer, the destination
  action `Add to export side panel`, and the unchanged-worksheet reminder.
- A route-controlled HTTP 500 write returned to Review, displayed the failure
  once, and required another explicit confirmation.
- After removing the controlled failure, the request order was:
  confirmation 200, write 500, fresh confirmation 200, separate write 200.
- Written showed one success treatment containing the exact answer and the
  actual side-panel destination.
- The landing rendered at 1440x900 and 390x844 with no browser console errors
  or warnings in the normal landing run.

The controlled 500 intentionally produced one browser network console error;
it is failure-path evidence, not a clean-console claim.

## Local verification completed

- `node --check frontend/app.js`
- `node --check frontend/ui-state.js`
- `npm run test:frontend`
- `python -m pytest tests/test_frontend_contract.py tests/test_static_assets.py -q`
- `git diff --check`

Results at this checkpoint:

- frontend checks passed;
- focused pytest: 20 passed;
- normal landing console: 0 errors, 0 warnings.

Full release lint, coverage, frontend CI, container build, and deployment
results:

- `python -m ruff check .`: passed.
- `python -m pytest tests/ --cov --cov-config=pyproject.toml
  --cov-report=term-missing`: 415 passed, 1 skipped; 83.65% coverage.
- `npm run ci:frontend`: passed.
- `git diff --check`: passed.
- Local `docker build -t claros:final .`: not run because the Docker Desktop
  Linux engine was unavailable. The tracked main-push workflow independently
  runs the production Docker build before deployment.

`npm ci` reported five known dependency advisories (two moderate, two high,
one critical). No dependency or runtime JavaScript package was added by this
frontend change, and no automatic audit rewrite was applied.

## Limits

This evidence uses a deterministic local synthetic fixture and local storage.
It does not establish live Gemini behavior, production GCS access, a Cloud Run
revision, or production write/export behavior.
