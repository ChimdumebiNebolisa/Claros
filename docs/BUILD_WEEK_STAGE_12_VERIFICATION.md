# Revamp Stage 12 verification

## Scope and provenance

- Base SHA: `22bc656` (`Merge pull request #30` — Stage 11 on `main`).
- Working branch: `codex/stage12-observability`.
- Scope: observability/performance hardening in application code — offload PDF
  parse and page render from the async event loop, content-free duration
  metrics, voice-connect metrics, and documented Cloud Run posture.
- **No production Cloud Run settings, secrets, or deploy configuration were
  changed in this stage.**

## Code changes

| Area | Change |
| --- | --- |
| Upload parse | `persist_assignment_from_pdf_bytes` runs via `asyncio.to_thread`. |
| Page render | PNG preview rendering runs via `asyncio.to_thread`. |
| Metrics | Optional bounded `duration_ms`; `page_render` and `voice_connect` events. |
| Docs | `DEPLOY.md` records recommended Cloud Run posture without applying it. |

## Deploy trigger warning

`.github/workflows/deploy.yml` runs on **push to `main`**. Merging this PR
would trigger that workflow. Stage 12 therefore opens a PR and **requires
explicit approval before merge**.

## Accepted P2

| Item | Owner |
| --- | --- |
| Distributed rate limits / spend controls across Cloud Run instances | Ops + product decision |
| Applying Cloud Run concurrency/timeout changes in GCP | Requires explicit approval |
| Full provider-cost metering beyond bounded events | Later observability pass |

## Deployment limitation

This stage intentionally does not alter live Cloud Run services or secrets.
