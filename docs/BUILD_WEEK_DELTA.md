# Build Week delta

> Historical-record notice: the legacy Build Week entries below describe
> candidate work from that period. In particular, OpenAI/GPT statements below
> are not claims about the current Claros runtime. Current runtime boundaries
> are maintained in `docs/ARCHITECTURE.md` and Stage 1 verification evidence
> is recorded in `docs/BUILD_WEEK_STAGE_1_VERIFICATION.md`.

## Revamp Stage 1 record

- Base/current committed SHA before Stage 1: `5c13307afe7488348ac1b25ffcd522de260333f3`
  (`Merge pull request #21 from ChimdumebiNebolisa/codex/claros-revamp-roadmap`).
- Working branch: `codex/stage1-runtime-safety`; Stage 1 changes are reviewed
  locally before any remote publication.
- Contributor evidence: current Codex task plus repository diff and test
  output. No unavailable session ID or exclusive authorship is claimed.
- Scope: Gemini-only production runtime consolidation; deterministic exact
  confirmed-answer stamping and export; provider/config and rate-limit
  failure handling; removal or gating of legacy debug/provider paths; browser
  injection regression coverage and baseline security headers.
- Evidence and remaining deployment uncertainty: see
  `docs/BUILD_WEEK_STAGE_1_VERIFICATION.md`.

## Revamp Stage 2 record

- Base/current committed SHA before Stage 2: `607636b`
  (`feat(runtime): consolidate Gemini safety boundary`).
- Working branch: `codex/stage2-canonical-model`, stacked locally on the Stage
  1 checkpoint pending intentional review and remote publication.
- Scope: replace the persisted flat `questions[]` source of truth with the
  versioned canonical document contract; preserve task/region/choice relations
  through extraction, session confirmation, writes, exports, and the client
  projection; retain only a quarantined migration adapter for older manifests.
  The contract now binds physical evidence to the source PDF, rejects
  overlapping/reused or out-of-frame writable evidence, and routes transformed
  coordinate frames to the side panel until a deterministic display transform
  is available.
- Contributor evidence: current Codex task plus repository diff and staged
  verification output. No unavailable session ID or exclusive authorship is
  claimed.
- Evidence and remaining deployment uncertainty: see
  `docs/BUILD_WEEK_STAGE_2_VERIFICATION.md`.

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
3. Phase 2 implementation is complete pending the required red-team review:
   assignment-scoped browser reset, high-entropy hashed assignment
   capabilities, protected page/review/delete/export routes, server-authorized
   written-answer export, production HMAC startup enforcement, bounded
   in-process upload/provider-session rate limits, and paginated side-panel
   export with explicit overflow failure.
4. Existing uncommitted code remains candidate work and is reviewed/staged by
   intent; no broad staging has been performed.

## Closed-world compiler slice

The default document path now builds deterministic physical evidence and sends
only that closed-world page input plus a rendered page image to the OpenAI
Responses/GPT-5.6 compiler. Its strict Pydantic result can select only supplied
block and response-candidate IDs. Deterministic materialization reconstructs
prompt text and geometry from those IDs and always sets `write_authorized` to
false. Provider, schema, or validation failure returns no model-authored task
data and leaves the page unresolved. The default is covered by mocks and local
container/browser smoke evidence; production activation remains blocked on a
Cloud Run OpenAI credential and usable project quota.

## Phase 2 red-team checkpoint

The required read-only red-team review found and drove repairs for three
issues: a potentially public debug-provider route, legacy plaintext session
compatibility, and incomplete expensive-route limits. Debug provider access is
now unavailable in production and development-only calls are rate-limited;
plaintext legacy session records cannot authenticate; and upload concurrency
plus capability-scoped write/review/page limits are in place. This remains an
in-process prototype limit, so production WAF/gateway controls are still an
external deployment task.

## Evidence rules

- Document-understanding evaluation is AI-adjudicated silver only. No human
  adjudication is claimed.
- Source PDF rights/privacy remain unresolved. Code can store local hashes and
  reproducible render instructions, but external PDFs remain local.
- OpenAI and deployment claims remain unverified until their offline, mocked,
and live checks are separately recorded in `docs/FINAL_VERIFICATION.md`.

## Silver benchmark scaffold

`evaluation/pdf_silver_benchmark/` now provides a local-only freeze manifest
for AI-adjudicated silver labels. It hashes structured metadata, requires a
source hash per page, and rejects altered labels. No source PDF, render, raw
provider payload, human annotation, or live adjudication result was added.
The existing `pdf_gold_pilot` remains legacy candidate work and is not treated
as gold by this execution because its own status records that human labels are
unavailable.

## Live evidence milestone status

The 17 selected pilot pages have been inventoried with local source-PDF hashes,
render availability, and physical-evidence counts. Fourteen pages have stable
physical block evidence; three image-only scans have no retained blocks or
response candidates and are visible input-blocked challenge cases. Independent
AI annotation contexts completed their first structured-output pass for the
fourteen available pages. The first live GPT-5.6 structured call reached the
provider and initially failed safely on a bounded-output truncation; the same
page succeeded after the schema-only retry raised the response bound.

The subsequent red-team/adjudication pass returned provider `RateLimitError`
before structured parsing. No final silver label, compiler prediction, or
promotion metric has been fabricated from those failures. Final freeze,
system comparison, and product compiler integration remain blocked until the
project has usable API capacity.

The controlled follow-up diagnosis classifies the provider response as HTTP
429 `insufficient_quota`: a billing/quota blocker, not a transient rate limit.
No live retry is permitted until the selected project has usable API capacity.
The local benchmark run ledger derives approximately `$3.636345` in estimated
cost from completed usage metadata under the versioned 2026-07-18 pricing
table. New requests are gated by `SILVER_BENCHMARK_MAX_COST_USD` (default
`$5.00`) before they are sent; provider cost was not claimed as reported.
