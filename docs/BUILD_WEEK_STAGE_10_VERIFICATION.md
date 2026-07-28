# Revamp Stage 10 verification

## Scope and provenance

- Base SHA: `b9fd751` (`Merge pull request #28` — Stage 9 on `main`).
- Working branch: `codex/stage10-test-rationalization`.
- Scope: test-suite audit and rationalization — remove dead/obsolete coverage and
  duplicate gates while preserving equal-or-stronger product-risk tests. No
  Stage 11 privacy rewrite and no Cloud Run changes.
- Contributor evidence: full suite inventory, removal/consolidation diff,
  pytest + frontend CI checks, independent red-team pass.

## Inventory baseline

- ~408 pytest tests under `tests/` (CI runs the full tree; no custom markers).
- 5 Node contract tests via `npm run ci:frontend`.
- Product spine kept: canonical_v1, canonical sample product flow, document
  pipeline, session/confirm/write APIs, worksheet/voice frontend contracts.

## Removals and consolidations

| Change | Product-risk rationale | Equal-or-stronger coverage retained |
| --- | --- | --- |
| Removed deprecated `WriteTokenParser` + its tests | Dead runtime; production uses confirm/write tokens | `test_write_api.py`, voice product-bridge, remaining `build_system_prompt` tests |
| Removed orphan `frontend/question-view.js` + serve route | Not loaded by `/app`; worksheet-view is the product surface | `worksheet-view` module serve tests + Stage 10 404 regression |
| Dropped duplicate unsupported-layout test from write-invariant file | Duplicate of parser/acceptance coverage | `test_parser.py`, `test_parser_acceptance_corrections.py` |
| Dropped duplicate `/test` 404 from main integration | Duplicate static-assets legacy-route check | `test_static_assets.py::test_legacy_debug_routes_are_disabled_by_default` |
| Removed `tests/test_frontend_contract.py` | Duplicate of npm `validate:frontend` | `npm run ci:frontend` / `scripts/validate_frontend.py` |
| Restored/strengthened Dockerfile module COPY gate | Docker smoke alone is weaker than COPY inventory | `test_dockerfile_copies_all_runtime_python_modules` (+ `sample_catalog.py` in Dockerfile) |
| Documented `test_parser.py` ownership | Steer new risks to canonical/pipeline suites | Canonical + document pipeline families |

## Red-team mutation checks added

| Mutation | Guard |
| --- | --- |
| Reintroduce orphan `/question-view.js` | `test_orphan_question_view_route_removed` expects 404 |
| Reintroduce `WriteTokenParser` | `test_deprecated_write_token_parser_removed` |

## Deferred (accepted P2)

| Item | Owner |
| --- | --- |
| Split oversized `test_document_pipeline.py` by risk domain | Later maintainability pass |
| Broader consolidation of legacy `parse_pdf` smokes | Only when hybrid-path coverage is proven stronger |
| Live Gemini / full AT matrix mutations | Stage 14 |

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 10.
