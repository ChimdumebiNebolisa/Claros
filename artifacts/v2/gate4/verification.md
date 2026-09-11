# Gate 4 semantic integration verification

Date: 2026-09-11
Branch: `codex/claros-v2-nerdy`

## Implemented checkpoint

- OpenAI Responses adapter with strict mapping and rephrase schemas, bounded
  output, `store: false`, no tools, and sanitized provider results.
- Closed-world block mapping with prompt-injection separation, seven required
  few-shot cases, exact server reconstruction, and post-schema validation.
- Explicit semantic engine/model/timeout/output configuration with a
  fail-closed API-key requirement when OpenAI semantics are selected.
- Application integration that keeps PDF parsing and geometry deterministic,
  gives the provider no coordinates, and records safe analysis failures.
- Opt-in rephrasing that keeps the current candidate unchanged until the
  student explicitly selects the suggestion, after which normal exact review
  and confirmation remain mandatory.
- Recorded-provider application coverage for direct typed and typed guided
  answers, rephrasing, selection, confirmation, and PDF export.
- Windows Docker smoke output is decoded explicitly as UTF-8 with replacement
  for malformed terminal bytes, avoiding locale-dependent reader failures.

OpenSpec tasks 4.1, 4.2, 4.3, and 4.5 are complete. Tasks 4.4, 4.6, and 4.7
remain open.

## Verification

| Check | Result |
| --- | --- |
| Focused Ruff over semantic, application, domain, and tests | Pass |
| Focused domain/semantic/application/OpenPDF-factory tests | 73 passed; 5 host qpdf skips |
| Pinned twelve-case corpus regeneration check | Pass |
| Corpus plus semantic tests | 76 passed |
| Applicable backend regression, excluding protected untracked Realtime tests | 453 passed; 16 host qpdf skips |
| OpenAI Python SDK adapter signature check | SDK 3.8.0 supports every used Responses parameter |
| `npm run ci` | Pass: format, lint, typecheck, dependency/license policy, API drift, 73 Vitest tests, Storybook accessibility, production build, and bundle closure |
| `npm run test:e2e:gate3` | Pass: one real Chromium/FastAPI authenticated typed/export/restart workflow |
| Linux production container build and real API smoke | Pass on Docker Engine 29.1.2 |
| `git diff --check` | Pass |

The container smoke evidence is in `artifacts/v2/gate4/container-smoke/`. It
records a non-root runtime, health, ownership isolation, privacy-safe logs,
typed flow, restart persistence, and valid inline and appendix exports.

## Remaining gate

No `OPENAI_API_KEY` or `CLAROS_OPENAI_API_KEY` was present. The required live
three-run corpus benchmark must still evaluate Luna, then Terra, then Sol as
needed and publish correctness, invalid-ID, p95 latency, token/cost, and chosen
model evidence. No model default is accepted for production until that gate
passes. No scanner, broad PDF-library search, production migration, deployment,
or traffic change was performed.
