# Revamp Stage 4 verification

## Scope and provenance

- Base SHA: `3cc8144` (`Merge pull request #22` — Stage 1–3 stack on `main`).
- Working branch: `codex/stage4-canonical-sample-flow`.
- Scope: make the three `canonical_v1` worksheets the official Claros sample
  system on the normal assignment path (`fetch sample PDF` → `POST /upload` →
  hybrid `parse_document` → session confirm/write/export/delete). No Stage 3
  parser changes, no expected-label edits, and no Stage 5 concurrency work.
- Contributor evidence: current Codex task, repository diff, focused API/UI
  regressions, browser inspection, and Stage 4 red-team notes below.

## Official sample catalog

> Historical note: Stage 4 exposed all three canonical fixtures. The current
> production contract supersedes that catalog and advertises only
> `canonical-short-answer-ecosystems`; the other two remain evaluation fixtures.

| Sample | `canonical_id` | Product entry |
| --- | --- | --- |
| Short Answer | `canonical-short-answer-ecosystems` | App chooser + `/app?sample=…` + landing CTA |
| Multiple Choice | `canonical-choice-digital-safety` | App chooser + deep link |
| Math Practice | `canonical-numeric-everyday-math` | App chooser + deep link |

Legacy `?sample=1` and `/sample-assignment.pdf` resolve to the Short Answer
sample. Root `test_assignment.pdf` remains a diagnostics-only algebra fixture
behind `ENABLE_DEBUG_ROUTES` and legacy parser tests; it is not the product
sample.

## Verified evidence

| Check | Result |
| --- | --- |
| Sample catalog + PDF/preview routes | Passed (`/api/samples`, `/samples/{id}.pdf`, previews). |
| Normal upload path (not demo parser) | Passed for all three samples; `parser != offline-synthetic-fixture-v1`. |
| Product-flow API matrix | Passed per sample: task targets, invalid-write retry, partial/full export, restore, deletion, replacement upload. Zero-answer export correctly returns 409. |
| Frontend contract | Passed (`scripts/validate_frontend.py` / `tests/test_frontend_contract.py`). |
| Browser inspection | App chooser shows Short Answer / Multiple Choice / Math Practice. Landing deep-links to Short Answer. With local storage, all three sample deep links complete `POST /upload` on `hybrid-physical-ir` and open the workspace (screenshots under `output/stage4-ui/`, not committed). |
| Stage 3 parser / expected labels | Untouched. |
| Independent Stage 4 red team | See findings below. |

## Independent review / red-team findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| S4-P1-1 | P1 | Deleted-assignment parse-diagnostics raised HTTP 404 then swallowed it into HTTP 500. | Fixed: re-raise `HTTPException` in diagnostics handler. |
| S4-P2-1 | P2 | Offline product-flow tests use the Stage 3 evidence selector; live Gemini semantics remain required for production sample task materialization when semantics are enabled. | Deferred to Stage 9 / live sample verification; samples still use the normal upload path. |
| S4-P2-2 | P2 | Checked-in `frontend/sample-workspace.png` is still a synthetic marketing asset, not a fresh capture of the three-sample chooser. | Deferred to Stage 7 visual polish; landing PDF preview now uses the official Short Answer page. |
| S4-P3-1 | P3 | Offline demo (`CLAROS_DEMO_MODE` + hero fixture) remains available for local demos and is intentionally separate from official samples. | Keep; documented. Not Stage 4 product samples. |

No remaining valid P0 findings.

## Retired assets

- Removed unused `tests/fixtures/parser/sample_assignment.pdf` and its labels
  JSON (no test references).
- Product sample routes no longer serve root `test_assignment.pdf`.

## Deployment limitation

Local Docker image smoke may still be environment-limited. Prefer remote CI
Docker verification on the Stage 4 PR.
