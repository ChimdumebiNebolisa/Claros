# Local worktree inventory

> **Historical snapshot (2026-07-18 on `build-week/claros-openai`).** Not the
> current `main` inventory or active plan. Present-tense roadmap:
> [`CLAROS_REVAMP_ROADMAP.md`](CLAROS_REVAMP_ROADMAP.md).

Recorded: 2026-07-18
Branch: `build-week/claros-openai`

This inventory preserves the state found before Build Week changes. It is a
classification record, not a claim that every candidate is production-ready.
No local work was stashed, reset, deleted, or copied into Git as part of this
inventory.

## Tracked modifications already present

| Classification | Paths |
| --- | --- |
| Production/runtime source | `assignment_service.py`, `config.py`, `exporter.py`, `main.py`, `manifest.py`, `ocr_adapter.py`, `parser.py`, `schemas.py`, `frontend/app.html`, `frontend/app.js`, `frontend/styles/app.css`, `frontend/worksheet-view.js` |
| Deployment/configuration | `.env.example`, `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `Dockerfile`, `pyproject.toml` |
| Documentation | `README.md` |
| Regression tests | `tests/test_assignment_api.py`, `tests/test_assignment_service.py`, `tests/test_exporter.py`, `tests/test_gcs_blob_selection.py`, `tests/test_layout_pipeline.py`, `tests/test_manifest.py`, `tests/test_parser.py`, `tests/test_session_api.py`, `tests/test_write_api.py`, `tests/test_write_invariant_characterization.py`, `tests/test_write_payload_validation.py` |

These files include pre-existing local changes and remain uncommitted at the
time of this record. They must be reviewed and staged by intent, not bundled
blindly with unrelated Build Week work.

## Important untracked material

| Classification | Paths | Handling |
| --- | --- | --- |
| Candidate source worth evaluating/integrating | `document_model.py`, `document_pipeline.py`, `semantic_classifier.py`, `review_service.py`, `ocr_adapter.py` changes | Preserve. Candidate pipeline is default-off; semantic classifier currently uses Gemini and requires migration to the closed-world provider interface. |
| Evaluation source and protocols | `evaluation/pdf_gold_pilot/`, `scripts/benchmark_pdf_pipeline.py`, `scripts/merge_pdf_benchmark_reports.py`, `tests/test_document_pipeline.py`, `tests/test_pdf_gold_pilot.py`, `tests/test_parser_acceptance_corrections.py`, `tests/fixtures/pdf_acceptance_expectations.json` | Preserve source and small fixtures. Rename/document as silver-only before publishing results. Do not add external PDFs. |
| Governing execution document | `docs/BUILD_WEEK_EXECUTION_PLAN.md` | Historical Build Week plan at inventory time (now labeled historical; not present-tense Claros roadmap). |
| Optional OCR dependency definition | `requirements-paddleocr.txt` | Preserve as an optional local dependency; do not make it a production default without separate performance and safety verification. |
| Generated benchmark/evaluation output | `output/pdf-benchmark-*`, `output/pdf-gold-pilot/`, `output/playwright/` | Retain locally; ignored because they contain derived corpus material, screenshots, and generated reports. Only reproduce/redact selected evidence with confirmed rights. |
| Local editor/tool state | `.cursor/`, `.impeccable/`, `.playwright-cli/` | Ignore and retain locally. Not application source. |
| Potentially private visual artifact | `screencapture-aave-2026-07-04-00_07_19.png` | Retain locally; do not commit without provenance/rights confirmation. |
| Local secrets | `.env` | Already ignored. Never inspect, stage, log, or commit values. |

## Corpus boundary

The 20-PDF/109-page corpus and the selected 17-page pilot source PDFs are
outside the repository or represented through generated local output. Their
publication rights and privacy status are unresolved. Repository evaluation
code may reference local inputs through hashes, page numbers, and documented
render instructions; it must not commit the external PDFs by default.

## Ignore policy added for Build Week

The repository now ignores generated output, local browser/editor state,
provider/OCR caches, and clearly named local/private corpus directories while
allowing the new durable Build Week and architecture documentation files.
Source code, schemas, evaluation code, and small reproducible fixtures remain
eligible for intentional review and staging.

## Canonical-path status at inventory time

| Area | Current active path | Candidate/dormant path |
| --- | --- | --- |
| PDF parser | `parser.parse_pdf_with_diagnostics` via `assignment_service.py` | `document_pipeline.parse_document`; `parser_layout.detect_layout_questions` is dormant |
| Manifest | `manifest.AssignmentManifest` v3 | Optional experimental `document` field |
| Exporter | `exporter.build_original_export_pdf` | `build_export_pdf` and `build_layout_export_pdf` are dormant |
| Voice | Gemini Live browser connection | No OpenAI Realtime adapter yet |
| Review/correction | Browser-local normalized region state | `review_service.py` is candidate-only and not authorization-safe |

The next phases establish the canonical physical IR and retire or explicitly
mark competing paths only after focused tests prove the migration.

## Build Week reconciliation update

Rechecked on 2026-07-18 before the live evidence milestone. Nothing was staged.

| Classification | Paths | Disposition |
| --- | --- | --- |
| Current Codex Build Week source | `rate_limit.py`, `providers/`, `document_compiler.py`, additions to `document_model.py`, security/session/export changes and their focused tests | Review as narrow security, compiler, and test commits after benchmark evidence is complete. |
| Current Codex Build Week evaluation code | `evaluation/pdf_silver_benchmark/`, `tests/test_pdf_silver_benchmark.py`, `tests/test_openai_semantic_compiler.py` | Source is eligible for review; generated labels, predictions, and raw agent outputs remain ignored/local. |
| Pre-existing local candidate work | `document_pipeline.py`, `semantic_classifier.py`, `review_service.py`, Paddle OCR changes, parser/layout candidates, benchmark scripts | Preserve and compare. Do not claim as current Codex work or stage without a path-specific review. |
| Generated/private local artifacts | `output/`, external corpus under Downloads, browser/editor state, `.env`, `screencapture-aave-2026-07-04-00_07_19.png` | Intentionally ignored or left untracked. Never stage. |
| Documentation | `README.md`, architecture/deployment changes, Build Week documents | Review separately; Build Week evidence documents are current work, while broader product-doc rewrites are uncertain until claims are verified. |
| Unrelated or uncertain | UI styling/landing changes, existing CI/deploy edits, optional OCR requirements | Leave uncommitted unless their individual intent and verification are established. |

The `.env` target is ignored and untracked. The local corpus, raw generated
benchmark output, browser profiles, and local provider material are also kept
out of Git. No classification authorizes staging by itself.
