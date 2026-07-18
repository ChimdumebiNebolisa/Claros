# Local worktree inventory

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
