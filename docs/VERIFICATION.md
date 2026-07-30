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

Production deployment evidence is pending. Before a production claim, record:

- deployed commit and Cloud Run revision;
- workflow run and immutable image;
- UTC timestamp and verifier;
- `/health`, `/`, `/app`, and shared-asset response evidence;
- functional provider/storage checks only when the required credentials are
  explicitly available; and
- remaining rollback or runtime uncertainty.

The GitHub Actions workflow provides static post-deploy smoke checks. Those
checks do not by themselves prove live worksheet parsing, storage access,
voice provider operation, write authorization, or export behavior.
