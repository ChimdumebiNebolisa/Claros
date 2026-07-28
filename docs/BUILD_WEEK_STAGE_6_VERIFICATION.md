# Revamp Stage 6 verification

## Scope and provenance

- Base SHA: `4d1bd1d` (`Merge pull request #24` — Stage 5 on `main`).
- Working branch: `codex/stage6-frontend-product-ui`.
- Scope: frontend architecture audit and product UI for the canonical document
  model. Keep vanilla JS; no framework migration; no Stage 7 visual redesign;
  no Stage 8 accessibility overhaul beyond clarity required for orientation.
- Contributor evidence: current Codex/Cursor task, Stage 6 audit, repository
  diff, frontend contract checks, and independent review notes below.

## Product UI changes

| Area | Behavior |
| --- | --- |
| Choices | Active-task structured choices render under the prompt when present. |
| Write step | Confirmed answer is shown read-only before the student chooses Write. |
| Progress | Task picker and multi-target chips show Not started / Draft / Confirmed / Written / Needs review. |
| Next step | `#answerProgress` states the current response status and next action. |
| Layout review | Visible informational notice when workspace is `needs_layout_review` (no student geometry editing). |
| Samples | Client aliases `1` / `default` / `true` to Short Answer; landing footer uses the canonical id. |
| Copy | Write voice state describes authorization for export placement, not silent PDF mutation. |

## Verified evidence

| Check | Result |
| --- | --- |
| Frontend contract | Passed (`python scripts/validate_frontend.py`) |
| UI-state / worksheet target Node tests | Passed via `npm run ci:frontend` (run before merge) |
| Dead `question-view.js` | Still served for compatibility; not loaded by `/app`. Removal deferred to Stage 10. |

## Independent review / red-team findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| S6-P0-1 | P0 | Write step hid the exact confirmed answer. | Fixed: `#confirmedAnswerPreview`. |
| S6-P0-2 | P0 | Task navigation lacked draft/confirmed/written progress. | Fixed in picker and multi-target chips. |
| S6-P0-3 | P0 | `needs_layout_review` was mostly screen-reader only. | Fixed: `#layoutReviewNotice`. |
| S6-P1-1 | P1 | Structured choices were not shown in the session panel. | Fixed: `#taskChoices`. |
| S6-P1-2 | P1 | Landing footer used `?sample=1` while client matched exact ids. | Fixed: canonical deep link + client aliases. |
| S6-P1-3 | P1 | Progress UI went stale after draft/reject/change; confirmed next-step ignored unsafe destinations. | Fixed: `refreshActiveProgress`; unsafe confirmed copy; needs-review prioritized in task badges. |
| S6-P2-1 | P2 | Monolithic `app.js` and dual response-state mirrors remain. | Deferred to Stage 10 rationalization / later modularization if needed. |
| S6-P2-2 | P2 | Orphan `question-view.js` remains served. | Deferred to Stage 10 test-suite cleanup. |

No remaining valid P0 findings for Stage 6 acceptance.

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 6.
