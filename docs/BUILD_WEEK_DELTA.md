# Build Week delta

## Provenance baseline

- Owner-confirmed contest start: `2026-07-13T09:00:00-07:00`
  (`2026-07-13T11:00:00-05:00`).
- Baseline command: `git rev-list -1 --before="2026-07-13T09:00:00-07:00" origin/main`
- Exact baseline: `7e3703286fe0f50d7839ae80fdf26f8ce73502f8`
  (`Merge final verification and privacy reconciliation`).
- Current Build Week branch: `build-week/claros-openai`.

The baseline supplied a PDF upload, deterministic parser/exporter path, Gemini
Live tutoring, and confirmation/write-token controls. It did not supply an
OpenAI document compiler, OpenAI Realtime migration, assignment-capability
authorization, or an AI-adjudicated silver benchmark.

## Attribution record

Git author/co-author metadata is evidence of attribution, not proof of who
performed every individual edit.

| Period/work | Evidence | Attribution statement |
| --- | --- | --- |
| CI and health-route fixes immediately after baseline | `a933a18`, `e54524e`, `8a69883`, `922f0cf`, `281220f`, `dfb4f97` | Authored by Cursor Agent; commits name Chimdumebi Nebolisa as co-author. |
| Worksheet layout/rebuild line | `0010ca5`, `663e35e`, `8de0751`, `fbf9288`, `1f7ab81`, `27d3e54`, `fb61652`, `6d37aa1`, `87ff0bf`, `d41c3d1`, `70a8712`, `e232daf` | Authored by Chimdumebi Nebolisa; several commits list Cursor as co-author. |
| Worktree preservation under this execution | `e9a2594`, `e23b8c9` | Created in the current Codex task. |
| Manual or unresolved provenance | Uncommitted tracked work and untracked candidate pipeline | Preserve and review by intent; no claim of exclusive Codex/Cursor authorship. |

The current primary Codex session ID is not available in repository evidence
and is deliberately not fabricated. The future `/feedback` session ID/output
is pending and must be added only after it exists.

## Build Week changes in progress

1. Phase 0 completed: created the Build Week branch, documented the dirty
   worktree, and ignored generated/private local artifacts without deleting
   them.
2. Phase 1 completed in documentation: baseline, architecture boundaries, and
   durable repository rules are recorded.
3. The next active implementation phase is P0/P1 assignment/session/export
   security repair. Existing uncommitted code is treated as candidate work and
   is verified before promotion.

## Evidence rules

- Document-understanding evaluation is AI-adjudicated silver only. No human
  adjudication is claimed.
- Source PDF rights/privacy remain unresolved. Code can store local hashes and
  reproducible render instructions, but external PDFs remain local.
- OpenAI and deployment claims remain unverified until their offline, mocked,
  and live checks are separately recorded in `docs/FINAL_VERIFICATION.md`.
