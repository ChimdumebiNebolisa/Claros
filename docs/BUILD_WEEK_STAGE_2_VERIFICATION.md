# Revamp Stage 2 verification

## Scope and provenance

- Base SHA: `607636b` (`feat(runtime): consolidate Gemini safety boundary`).
- Working branch: `codex/stage2-canonical-model`, stacked locally on the Stage
  1 checkpoint pending intentional review and remote publication.
- Scope: one authoritative production document contract, quarantined legacy
  migration, task/region/choice relations through persistence and export, and
  coordinate/source-integrity safety. No live Gemini, GCS, or production
  deployment claim is made by this record.
- Contributor evidence: the current Codex task, repository diff, independent
  red-team findings, and the checks below. No unavailable session ID or
  exclusive authorship is claimed.

## Verified evidence

| Check | Result |
| --- | --- |
| `python -m ruff check .` | Passed. |
| `python -m pytest tests/ --cov --cov-config=pyproject.toml --cov-report=term-missing` | Passed: 286 tests; 81.34% total coverage (72% required). |
| `npm run ci:frontend` | Passed: frontend session/UI/worksheet security and response-target tests, frontend contract validation, and GenAI bundle build. |
| `git diff --check` | Passed. |
| Local Playwright browser flow | Passed against an isolated local demo configuration: actual fixture upload, task display, typed draft, review, explicit confirmation, separate write action, and PDF export. The downloaded export had two pages and contained the confirmed answer on a side-panel page; the original worksheet page remained unchanged. |
| Coordinate safety regressions | Passed for rotated pages, non-default crop, `/UserUnit`, display-frame OCR, crop-edge content, and off-page vector geometry. Invalid or transformed physical targets stayed bounded and routed to the side panel. |
| Independent Stage 2 red team | No P0/P1 remained after fixes. It rechecked candidate ordering, source binding, canonical evaluation adaptation, task display/voice lookup, export/review transform gates, and the coordinate adversarial cases. |

## Design evidence

1. `IntermediateDocument` v2 is the sole persisted production document model.
   It owns pages, source blocks, tasks, choices, independent response-region
   entities, and explicit task-to-response links. Mutable draft, confirmation,
   token, and write state is separate session state.
2. Legacy flat manifests are migrated in memory as quarantined,
   side-panel-only evidence. They are not a parallel persisted model.
3. Approved regions require one contained, eligible physical source block;
   duplicate/reused sources, interior overlaps, invented source text, invalid
   relationships, and unsafe transformed placements fail closed.
4. The canonical evaluation adapter assembles only actual contiguous pages
   from one source PDF. Its labels remain AI-adjudicated silver; no human gold
   or correctness claim is made.

## Deployment limitation

`docker build -t claros:final .` could not run because the local Docker Desktop
Linux-engine named pipe was unavailable. This is an environment limitation, not
evidence of a successful container build; container runtime verification
remains pending a running Docker daemon.
