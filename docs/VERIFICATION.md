# Verification

This file points to current verification evidence. Local deterministic evidence
is not provider or production evidence.

## Current frontend evidence

The current workspace and landing evidence record is:

`docs/evidence/FRONTEND_SIMPLIFICATION_2026-07-29.md`

It records the mainline integration base, real product-state capture hashes,
desktop and mobile checks, confirmation/write request separation, failed-write
recovery, and local test results.

## Production status

The frontend simplification release is deployed:

- commit:
  `bc23357c4703bd0dad33be5921c51d6d6df24ed3`;
- Cloud Run service and revision:
  `claros` / `claros-00060-f48`, serving 100 percent of traffic;
- immutable image:
  `gcr.io/<GCP_PROJECT_ID>/claros:bc23357c4703bd0dad33be5921c51d6d6df24ed3`,
  digest
  `sha256:5df9e1e603dbcad9a59718d70b74d57dd0bbce4b82882980304f54ffc840eee8`;
- deployment workflow:
  [GitHub Actions run 30513131324](https://github.com/ChimdumebiNebolisa/Claros/actions/runs/30513131324),
  completed successfully at `2026-07-30T04:14:25Z`;
- production URL verified:
  `https://claros-fnaobzrxeq-uc.a.run.app`;
- verifier:
  the tracked GitHub Actions deploy workflow plus the current Codex task;
- direct response evidence at `2026-07-30T04:15:35Z`:
  `/health`, `/`, `/app`, `/styles/tokens.css`,
  `/sample-workspace-review.png`, and
  `/fonts/instrument-sans-latin-wght-normal.woff2` each returned HTTP 200
  with the expected content type; and
- content probes found the current landing hero and Review capture, found the
  mobile view switch in `/app`, and did not find the removed visible Reject
  control.

The workflow's tests, production image build, deployment, and static smoke
checks all passed. This evidence does not establish live worksheet parsing,
production storage access, voice provider operation, write authorization, or
export behavior; those require separate credentialed functional verification.
