# Revamp Stage 11 verification

## Scope and provenance

- Base SHA: `3905da6` (`Merge pull request #29` — Stage 10 on `main`).
- Working branch: `codex/stage11-security-privacy`.
- Scope: security, privacy, and lifecycle honesty — assignment delete reliability,
  capability-safe legacy manifests, session restore authorization, retention
  documentation, and content-free upload errors. No Cloud Run deploy or secret
  rotation.
- Evidence: lifecycle tests, session/assignment suite updates, storage doc rewrite.

## Fixes

| Area | Change |
| --- | --- |
| Delete reliability | `session_cleanup` / `assignment_delete` metrics are valid; session cleanup failures cannot block prefix delete. |
| Session refs | Expired sessions unregister `.ref` markers; delete unregisters refs. |
| Delete API | Assignment delete works when PDF is gone but manifest/session markers remain. |
| Legacy backfill | No capability-less signed manifest is persisted. |
| Restore auth | `SessionRestoreRequest.assignment_id` required; capability checked before session load; mismatch → 403. |
| Upload errors | `PDFProcessingError` returns a fixed client message (no raw exception text). |
| Retention docs | `STORAGE_ARCHITECTURE.md` distinguishes logical assignment expiry from physical delete. |

## Verified evidence

| Check | Result |
| --- | --- |
| Lifecycle unit tests | `tests/test_assignment_lifecycle.py` |
| Session/assignment suites | Focused pytest below |
| Frontend restore contract | `assignment_id` included in restore body |

## Accepted P2

| Item | Owner |
| --- | --- |
| Distributed rate limits / multi-instance abuse controls | Stage 12 |
| Automatic physical purge on assignment TTL | Product decision + Stage 12/ops if approved |
| Dependency vulnerability CI (`pip audit` / `npm audit`) | Stage 12 hardening |

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 11.
