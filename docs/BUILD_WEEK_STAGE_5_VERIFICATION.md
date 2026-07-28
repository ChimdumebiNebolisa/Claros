# Revamp Stage 5 verification

## Scope and provenance

- Base SHA: `a383f8a` (`Merge pull request #23` — Stage 4 on `main`).
- Working branch: `codex/stage5-state-write-integrity`.
- Scope: state, confirmation, writing, refresh restoration, retries,
  concurrency primitives, and export integrity. No Stage 6 frontend redesign,
  no Stage 7 visual polish, and no canonical fixture/label edits.
- Contributor evidence: current Codex/Cursor task, repository diff, focused
  API regressions, frontend contract checks, and independent Stage 5 red-team
  notes below.

## Integrity changes

| Area | Behavior |
| --- | --- |
| Confirm | Re-confirm clears outstanding write tokens; different text clears stale `written_answer`. |
| Restore | Confirmed-but-unwritten targets receive a fresh `write_token` without retyping. |
| Reauthorize | `POST /api/session/{id}/reauthorize-write` reissues authorization after refresh/retry. |
| Write | Token consume + `mark_written` persist in one step; successful same-answer retries are idempotent. |
| Export | Still requires at least one written answer (409 when zero). Placement revalidation remains export-time. |
| Delete | Assignment delete removes registered session blobs via `session-*.ref` markers. |
| Frontend | Restore restores tokens and active task/target; write failures no longer clear server-aligned confirmation. |

## Verified evidence

| Check | Result |
| --- | --- |
| Session confirm/restore/reauthorize/write | Passed (`tests/test_session_api.py`) |
| Write API invariants | Passed (`tests/test_write_api.py`, `tests/test_write_invariant_characterization.py`) |
| Local session lifecycle cleanup | Passed (`tests/test_local_storage.py`) |
| Canonical sample product flow | Passed (`tests/test_canonical_sample_product_flow.py`) |
| Frontend contract | Passed (`scripts/validate_frontend.py`) |

## Independent review / red-team findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| S5-P1-1 | P1 | Refresh left confirmed answers without a usable write token. | Fixed: restore reissues tokens; reauthorize endpoint added. |
| S5-P1-2 | P1 | Write path consumed the token before marking written. | Fixed: `authorize_confirmed_write` single persist step + idempotent success retry. |
| S5-P1-3 | P1 | Re-confirm left stale `written_answer` / pending tokens. | Fixed in `SessionState.set_confirmed`. |
| S5-P1-4 | P1 | Frontend cleared `confirmed` on any write error. | Fixed: preserve confirmation; reauthorize on 403; surface conflicts. |
| S5-P1-5 | P1 | Session registration failures were swallowed, leaving undeletable sessions. | Fixed: create_session rolls back and returns 500. |
| S5-P1-6 | P1 | Restore persist conflicts cleared browser session credentials. | Fixed: server retries once; client retries 409 and clears only on 403/404/410. |
| S5-P2-1 | P2 | Zero written answers still return export HTTP 409. | Accepted: coherent fail-closed product policy; UI already blocks with a clear message. Stage 6 may refine copy only. |
| S5-P2-2 | P2 | Logical write still does not mutate the PDF until export. | Accepted/documented: export-time placement revalidation remains the safety boundary. Stage 6 copy already clarified. |
| S5-P3-1 | P3 | Restore response map remains keyed by `response_region_id` alone. | Deferred to Stage 10/11 unless duplicate region IDs appear in production model. |

No remaining valid P0 findings. Independent Bugbot review of the Stage 5 diff
confirmed the registration and restore-conflict issues above; both are fixed
with regression coverage.

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 5. Prefer remote CI Docker verification on the Stage 5 PR.
