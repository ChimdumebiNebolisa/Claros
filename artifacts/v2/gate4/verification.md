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

OpenSpec tasks 4.1 through 4.6 are complete. Task 4.7 remains open pending the
independent read-only review and checkpoint recording.

## Live model selection

The first bounded live sweep used the frozen model order and three runs per
candidate. Luna was closest at 32/33 correct, zero invalid IDs, and 4,834 ms
p95; Terra produced 27/33 correct with 4,507 ms p95; Sol produced 26/33 correct
with 6,162 ms p95. No candidate was selected from that fingerprint.

The single Luna miss was a `semantic_overlapping` failure on the synthetic
non-science fixture. The system instructions were narrowed to state the
already-enforced postvalidation rules explicitly: prompt and context IDs are
disjoint, question prompts cannot be reused as context, and shared instructions
require the warning on every referencing question. No schema, validator, gold
expectation, or acceptance threshold changed.

The required three-run benchmark was then repeated from Luna against the new
prompt fingerprint. Luna passed all 33 required model-addressable results with
zero invalid IDs and 5,347 ms p95 latency against the configured 30,000 ms
semantic timeout budget. It used 135,678 input tokens and 7,534 output tokens,
with an estimated cost of $0.036176 at the recorded 2026-09-11 price. The runner
stopped immediately; Terra and Sol were not called again. The checksum-pinned
scan-only case remains a deterministic preflight rejection and was not sent to
a model.

The sanitized per-fixture evidence is in `live-model-benchmark.json`. It stores
case IDs, safe failure codes, counts, latency, token usage, cost estimates, and
fingerprints. It stores no API key, provider payload, or generated text.

## Verification

| Check | Result |
| --- | --- |
| Focused Ruff over backend, scripts, and tests | Pass |
| Focused semantic tests after the live prompt correction | 53 passed |
| Pinned twelve-case corpus regeneration check | Pass |
| Corpus plus semantic tests | 76 passed |
| Applicable backend regression, excluding protected untracked Realtime tests | 454 passed; 16 host qpdf skips |
| OpenAI Python SDK adapter signature check | SDK 3.8.0 supports every used Responses parameter |
| `npm run ci` | Pass: format, lint, typecheck, dependency/license policy, API drift, 73 Vitest tests, Storybook accessibility, production build, and bundle closure |
| `npm run test:e2e:gate3` | Pass: one real Chromium/FastAPI authenticated typed/export/restart workflow |
| Live Luna benchmark | Pass: 33/33 correct, zero invalid IDs, 5,347 ms p95 |
| Credential and artifact scan | Pass: server key authenticated; benchmark evidence contains no key or generated text |
| Linux production container build and real API smoke | Pass on Docker Engine 29.1.2 |
| `git diff --check` | Pass |

The container smoke evidence is in `artifacts/v2/gate4/container-smoke/`. It
records a non-root runtime, health, ownership isolation, privacy-safe logs,
typed flow, restart persistence, and valid inline and appendix exports.

## Remaining gate

The live-model blocker is cleared and `gpt-5.6-luna` is the selected semantic
default. Gate 4 closes after the independent read-only review records no
unresolved critical finding and `docs/v2/STATUS.md` records the content
checkpoint. No scanner, broad PDF-library search, production migration,
deployment, or traffic change was performed.
