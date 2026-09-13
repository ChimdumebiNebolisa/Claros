# Claros V2 Delivery Status

- **As of:** 2026-09-12
- **Branch:** `codex/claros-v2-nerdy`
- **Baseline:** `5fb217715e4b3278f21a882b2652d928f2cca628`
- **Current phase:** Gate 5 in progress — browser acceptance and scoped code review pass; final human microphone/PDF acceptance remains
- **Gate state:** Gates 0–4 passed; Gate 5 is 11/13 tasks complete
- **Gate 0 content checkpoint:** `0c15404b87edbbe19b03de93d81ad95aa1e897fd`
- **Gate 1 content checkpoint:** `59cbc509650cc4a65b139a7db23012ead74efb3c`
- **Gate 2 content checkpoint:** `0723303ef718bb28594d519da31ec0a55226fa45`
- **Gate 3 accepted clean checkpoint:** `88cda664f55abf698a1d56567e814e024708ad0a`
- **Gate 4 accepted evidence checkpoint:** `976e176ea0fe828147684757ae7cf07e37a1e175`
- **Gate 4 live-source checkpoint:** `121287e766140610dfdde8cddfd3cec36817d6b0`
- **Gate 5 workspace-integration checkpoint:** `2c688e58f197127f62571fa68fc797a4986fbaca`
- **Gate 5 live-defect checkpoint:** `22b3d602d5b02711d0997af4fe18ce8945484cf5`
- **Gate 5 browser-acceptance implementation checkpoint:** `06425f913df328a21abeb73b192760005cee7d34`
- **Gate 5 scoped independent code-review checkpoint:** `06425f913df328a21abeb73b192760005cee7d34` — approved; human evidence still pending
- **Gate 5 conversation-behavior implementation checkpoint:** `bcede3835f0512e964c257a48a6a627ece4b1d11` — application behavior evaluated; final direct-answer policy live rerun pending

### 2026-09-12 conversation-behavior repair

The effective live policy and tool schemas now come from one shared artifact
consumed by FastAPI and the real browser agent, with an SDK-level effective
configuration test preventing server/browser drift. Application-owned state
updates distinguish local/persisted drafts, exact review, approval, export,
failure, active question, version, revision, and context epoch. Tools await a
bounded correlated workspace outcome; relative navigation resolves from the
actual active question and is acknowledged only after actor acceptance.

Six bounded typed `gpt-realtime-2.1` sessions preserved four policy failures
instead of selecting only successful retries. The first drove removal of
duplicate action framing; later runs exposed a complete disguised answer and
then a partial sentence frame. The sixth/final run removed the frame but still
embedded the pasteable clause “plants need sunlight to power the process that
makes their food.” Independent review correctly rejected the initial pass
classification. Policy `2026-09-12.5` now requires a focused question without
stating the conclusion while preserving concept explanations for concept-help
turns. The six-session cap prevents claiming a post-`.5` live pass. Known-
answer capture and the live local/not-approved/not-exported status response did
pass.

At policy checkpoint `bcede38`, 110 frontend tests and 76 backend Realtime
tests pass, along with lint, typecheck, formatting, strict OpenSpec, and
whitespace checks. At unchanged application/PDF checkpoint `6004c8a`, 10
isolated real-application Chromium tests and 22 zero-skip OpenPDF tests also
pass, along with OpenAPI drift. Full details, exact excerpts, rejected
hypotheses, and evidence classifications are in
`artifacts/v2/gate5/conversation-behavior-repair.md`. Tasks 5.7 and 5.8 remain
open for physical-microphone, human-audible-playback, and downloaded-PDF
acceptance. No merge or deployment was performed.

### 2026-09-11 product-owner correction

Mandatory direct/guided selection and fixture-default `/app` behavior are
superseded. The three authority files and active OpenSpec change now specify one
adaptive conversation using the real runtime by default. Authority SHA-256:

- Execution PRD: `17F7CBD11691A7DD97195AF45F98A2E9B8910921F805FC2CDC037D6963F8997F`
- Product contract: `E0D00CE25E2806AF4BCE8997A798C7504667910A9A770F7B599131904C14B01E`
- Design system: `23B8789FB543B0C14F41940D5DBD68FEB7BE851517CB8757CBE8748B023FF374`

Reason: the product owner rejected separate answer modes and authorized a
targeted restoration of one real conversation while retaining all approval,
authorization, immutable-source, deterministic-placement, and PDF-validation
invariants.

### 2026-09-12 scoped conversation-audit correction

The authority text now removes the remaining mandatory-path contradiction and
defines known-answer and guided-help behavior as intents inside one adaptive
conversation. OpenSpec task 5A.5 is complete. Verification passed with 46
focused frontend conversation tests, 129 focused backend Realtime/semantic
tests, 531 full backend tests (17 OpenPDF tests skipped because local `qpdf` is
unavailable), 103 full Vitest tests, the all-story Playwright axe sweep, the
production build/bundle boundary checks, Ruff, strict OpenSpec validation, and
zero npm audit vulnerabilities. The deployment workflow now depends on the
offline conversation gate.

That legacy `npm run test:e2e` failure was reproduced before repair: it started
the wrong runtime, attempted to reach an unstarted API on port 8080, and still
expected fixture-default behavior. The suite now owns an isolated real FastAPI
and OpenPDF runtime on port 18080 and passes against the actual V2 application.
Physical microphone and human PDF acceptance remain open under tasks 5.7 and
5.8.

### 2026-09-12 Gate 5 browser-acceptance repair

Implementation checkpoint `06425f9` repairs the Playwright launcher in place,
maps useful legacy assertions to the one-conversation product, and covers the
real landing, assignment, review, authorized confirmation, and OpenPDF export
paths. Only the external Realtime boundary is replaced in the test build by
deterministic event replay. The repair also pauses capture after terminal
disconnect, rejects old question/version/generation events, and keeps
typed-only `Hear it` playback completion usable after version advancement.

Fresh verification at this implementation shape passed 48 conversation tests,
105 full frontend tests, 10 real-application Chromium tests, 548 backend tests
with zero skips, 22 focused OpenPDF publication tests with zero skips, and the
all-story accessibility sweep. Format, lint, typecheck, production build,
bundle boundaries, dependency/API contracts, Ruff, strict OpenSpec, secret
scans, and npm audit also passed. A separate read-only reviewer approved exact
SHA `06425f9` after two correction passes. The combined evidence and human
checklist are in `artifacts/v2/gate5/live-acceptance.md`.

### 2026-09-12 one-agent implementation evidence

`npm start` now serves the real FastAPI/Vite/OpenAI/OpenPDF application at
`http://127.0.0.1:8080/app`; fixture scenarios remain development/test-only.
The biology sample and a separately uploaded supported PDF both traversed the
real assignment, provider, candidate, exact-review, confirmation, placement,
export, download, qpdf, and extracted-text checks. A provider-requested move
from question 2 to question 3 was application-validated and preserved the
conversation turn. The adapter-to-workspace regression suite covers completed
transcript ownership, answer-draft binding, independent input/output mute,
non-destructive interruption, reconnect context, and grounded navigation.

This environment could establish a real OpenAI WebRTC session and observe the
assistant response transcript/audio-output lifecycle, but it could not supply
human speech to a physical microphone or have a human confirm audible playback.
Those two sensory checks remain unverified and do not close tasks 5.7 or 5.8.

## Current milestone

- **Gate 4 checkpoint:** All seven tasks pass. `gpt-5.6-luna` is selected after
  33/33 live corpus results, zero invalid IDs, 7,142 ms p95 latency, and one
  accepted live rephrase. The sanitized report is bound to clean source
  checkpoint `121287e` and checksum-verifies every fixture before a model call.
- **Gate 4 review:** Independent review at evidence checkpoint `976e176` found
  no remaining P0–P3 issue after verifying source/tree binding, corpus and
  prompt/schema fingerprints, adversarial prompt separation, provenance,
  stale-rephrase prevention, output redaction, and report consistency.
- **Gate 5 credential boundary:** The preserved server-side Realtime draft is
  integrated. Credential issuance now validates the signed owner session,
  assignment expiry, active question, requested mode, exact assignment version,
  and rate limit before returning only a 60-second `ek_` client credential.
  Focused policy, provider, lifecycle, authorization, and service tests pass.
- **Gate 5 browser adapter:** `@openai/agents` 0.18.0 is pinned and isolated
  behind the existing Realtime lazy boundary. The WebRTC adapter accepts only
  the server-issued `ek_` credential, maps provider events to visible voice
  states and captions, validates narrow tool inputs against trusted turn IDs,
  supports typed turns, mute, stop, interrupt, and exact playback, deduplicates
  provider events, closes SDK-owned media on replacement/exit, and permits one
  automatic reconnect. The existing fake adapter remains deterministic.
- **Gate 5 workspace binding:** Voice and typed turns now share one adaptive
  conversation using the live lazy-loaded adapter in API mode. Candidate writes retain the
  authorized Realtime session/source-turn evidence, exact voice confirmation
  routes through the existing confirmation mutation only in exact review, and
  microphone/connection/module failures preserve the draft and expose typed
  continuation. Tasks 5.3–5.6 pass at checkpoint `2c688e5`.
- **Gate 5 live acceptance:** Live guided responses, full caption/turn
  persistence, mute, interruption, post-interrupt continuation, credential
  failure/retry, and direct connect/stop pass at `22b3d60`. The run fixed the
  provider safety-identifier limit, text-only WebRTC input track, speaking/stop
  state, multipart response finalization, API-mode navigation, and
  cross-question captions. A human-spoken direct transcript/candidate and live
  spoken exact-confirmation phrase remain unverified, so tasks 5.7 and 5.8 stay
  open. The current deterministic application-browser suite and scoped code
  review pass at `06425f9`; neither is represented as sensory evidence. See
  `artifacts/v2/gate5/live-acceptance.md`.

- **OpenPDF promotion:** The validated Java renderer is integrated behind
  explicit `CLAROS_PDF_ENGINE=openpdf` selection in the real `/api/v2` service.
  OpenPDF output is quarantined behind qpdf and PDFBox; PDF.js is a CI/release
  compatibility check only. The Cloud Run template remains explicitly set to
  `current`, and no deployment or infrastructure mutation is part of this work.
- **Promotion verification:** Focused real-endpoint and failure-path tests pass
  locally with Java 21.0.10, OpenPDF 3.0.5, PDFBox 3.0.8, qpdf 12.3.2, and the
  allowlisted Noto Sans Regular font. Clean-worktree, real-browser, sample PDF,
  PDF.js release compatibility, resource timing, and failure-injection evidence
  are recorded in `artifacts/v2/openpdf-migration/verification.md`. Task 3.11 is
  complete; Docker/production activation remains separately blocked and
  unauthorized.

- **Milestone:** Gate 3 passed at accepted clean checkpoint `88cda66`.
- **Changed:** Added the FastAPI `/api/v2` service, signed anonymous ownership,
  filesystem/GCS adapters, generation-CAS manifests, generated browser types,
  deterministic physical IR and placement, immutable-source inline/appendix
  export, gold corpus, real typed browser integration, and deployment assets.
- **Verified:** Node 22 CI and browser suites passed; 392 tracked Gate-3-only
  backend tests passed at 92-percent branch coverage; audits, strict OpenSpec,
  Terraform validation, authority hashes, Chrome/pikepdf/Acrobat reopening,
  Ubuntu production-container restart, Cloud Build, and live GCS/Cloud Run
  revision replacement all passed.
- **Remote evidence:** GitHub run `33941739290` retained privacy-safe logs and
  both synthetic PDFs. Cloud Build `8bcf24be-5be9-4e81-a8e5-fc2947d39754`
  produced digest `sha256:b4058b7bb22210a82690db7859354dad4fdf354441d57ee46a79deea6d7d5b66`;
  revision `claros-00075-xtv` serves it at 100 percent after live persistence,
  ownership-isolation, and proxy-identity checks.
- **Next action:** Run the seven-step physical-microphone checklist in the
  prepared local application, including audible playback and downloaded-PDF
  inspection. If it passes, append the observations, close task 5.7, and ask
  the independent reviewer to close the evidence portion of task 5.8. Do not
  include the unrelated Docker artifacts.

## Gate 0 checklist

- [x] Use `codex/claros-v2-nerdy` from exact commit `5fb2177`.
- [x] Copy all three V2 authorities to the repository root byte-for-byte.
- [x] Verify all three SHA-256 values.
- [x] Read all three authorities in full and apply their authority order.
- [x] Preserve prior audit findings; record only the V2-invalidated delta.
- [x] Create `docs/v2/BASELINE_AUDIT.md`.
- [x] Create `docs/v2/CONFLICTS.md`.
- [x] Create `docs/v2/DECISIONS.md`, including dependencies and ownership.
- [x] Create `docs/v2/RISKS.md`.
- [x] Create `docs/v2/STATUS.md`.
- [x] Rewrite the active OpenSpec capabilities and task graph in place.
- [x] Preserve the V1 17/19 history as disposition, not V2 progress.
- [x] Run and record `openspec validate claros-reconstruction --strict`.
- [x] Run and record post-synthesis baseline regression checks.
- [x] Run and record `npm audit --audit-level=high`.
- [x] Verify current screenshot evidence still exists.
- [x] Inspect dependency and production-source diffs; both are unchanged.
- [x] Run and record `git diff --check`.
- [x] Complete an independent read-only authority/OpenSpec contract review with
      no blocking contradiction found.
- [x] Commit the Gate 0 planning-only checkpoint.

## Prior baseline evidence

The following passed on the unmodified baseline before the V2 authority delta:

| Evidence                                                  | Result                    |
| --------------------------------------------------------- | ------------------------- |
| `npm run build`                                           | Pass                      |
| `npm test`                                                | Pass — 7 tests            |
| `npm run test:e2e`                                        | Pass — 4 Playwright tests |
| `npm run build-storybook`                                 | Pass                      |
| Pre-V2 `openspec validate claros-reconstruction --strict` | Pass                      |

The existing browser evidence is in `test-results/`: landing desktop/mobile,
workspace desktop, and mobile worksheet/answer states. It is retained only as
the V1 baseline. Gate 2 produces the full V2 matrix under
`artifacts/v2/screenshots/`.

## Fresh Gate 0 verification — 2026-09-04

| Command/evidence                                      | Result                                                                   |
| ----------------------------------------------------- | ------------------------------------------------------------------------ |
| `npm ci`                                              | Exit 0; 357 packages installed; install audit reported 0 vulnerabilities |
| `npm run ci`                                          | Exit 0; production build passed and 7/7 Vitest tests passed              |
| `npm run build-storybook`                             | Exit 0; static Storybook build completed                                 |
| `npm run test:e2e`                                    | Exit 0; 4/4 Chromium Playwright tests passed                             |
| `npm audit --audit-level=high`                        | Exit 0; 0 vulnerabilities                                                |
| `openspec validate claros-reconstruction --strict`    | Exit 0; change valid                                                     |
| Authority SHA-256 checks                              | All three exact expected hashes matched                                  |
| `Get-ChildItem -Recurse .\test-results -Filter *.png` | Existing V1 browser screenshots present                                  |
| Production/dependency diff                            | Empty for `package.json`, lockfile, `src`, and `server`                  |
| Authored-file `git diff --check`                      | Exit 0; no whitespace errors                                             |
| Independent read-only contract review                 | No blocking authority, governance, or OpenSpec contradiction found       |

The verbatim authority imports contain ten intentional Markdown hard-break
lines with trailing double spaces. `git show --check 0c15404` reports those
lines. They are preserved because changing them would violate the required
byte-for-byte hashes; all authored Gate 0 files pass the whitespace check.

## Fresh Gate 1 verification — 2026-09-04

All commands in this table used Node `v22.23.2` where Node was involved.

| Command/evidence                                   | Result                                                                                                                                                        |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm ci`                                           | Exit 0; clean install of 763 packages; install audit reported 0 vulnerabilities                                                                               |
| `npm run ci`                                       | Exit 0; format, lint, typecheck, dependency/license contract, 27/27 Vitest tests, Storybook build, Storybook axe, production build, and bundle closure passed |
| `npm run test:e2e`                                 | Exit 0; 7/7 Chromium tests passed against fresh development and production servers                                                                            |
| `npm audit --audit-level=high`                     | Exit 0; 0 vulnerabilities                                                                                                                                     |
| `npm run check:dependencies`                       | Verified 17 exact versions/licenses, seven approved Untitled primitives, Node 22 engine, and retained legacy dependencies                                     |
| `npm run check:bundles`                            | Verified four marketing entry chunks exclude PDF/Realtime and all lazy boundaries exist                                                                       |
| Authentic document evidence                        | `renderPageRect` crop and full EmbedPDF viewer rendered the checked-in PDF through byte Range requests                                                        |
| Accessibility/keyboard evidence                    | Seven V2 Storybook states passed axe; upload and modal flows passed keyboard, focus restoration, 44px target, and mobile-overflow assertions                  |
| CSP/WASM/worker evidence                           | Built app loaded PDFium WASM and worker under production CSP; `/` made no PDF/Realtime request                                                                |
| `openspec validate claros-reconstruction --strict` | Exit 0; change valid                                                                                                                                          |
| Authority SHA-256 checks                           | All three exact expected hashes still match                                                                                                                   |
| `git diff --check`                                 | Exit 0; no whitespace errors                                                                                                                                  |
| Independent read-only Gate 1 review                | Approved with no critical/blocking finding; vendor-upgrade risk retained in `RISKS.md`                                                                        |

The production and Storybook builds report two accepted pinned-EmbedPDF
warnings: browser externalization of a package `crypto` import and large lazy
viewer chunks. Real crop/full-view execution passes in Chromium under the
production CSP, and the marketing static closure contains neither stack. Gate 6
must repeat this proof before cutover.

## Fresh Gate 2 verification — 2026-09-04

All Node commands in this table used Node `v22.23.2`. Browser evidence and the
visual scorecard are bound to content checkpoint
`0723303ef718bb28594d519da31ec0a55226fa45`.

| Command/evidence                                   | Result                                                                                                                                                                                             |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run ci`                                       | Exit 0; format, lint, typecheck, dependency/license contract, 63/63 Vitest tests, Storybook build, all-story axe, production build, and bundle closure passed                                      |
| Storybook browser sweep                            | 36/36 V2 stories rendered; zero automated accessibility violations                                                                                                                                 |
| `playwright test`                                  | Exit 0; 22/22 serialized Chromium tests passed against fresh Vite/API servers in 3.1 minutes                                                                                                       |
| Direct and guided workflows                        | Exact review remained mandatory; casual voice agreement could not confirm; typed fallback, captions, interruption, rephrase selection, revision, and reconfirmation passed                         |
| Partial export and recovery                        | Export became available after one confirmed answer; unanswered questions remained blank; failure retry and authenticated fixture download passed                                                   |
| Authentic document evidence                        | Question-bound Q1/Q2/Q3 EmbedPDF crops, completed-copy preview, byte-Range source, decoded mobile full viewer, and source-preservation copy passed                                                 |
| Responsive/accessibility evidence                  | Task-first DOM order, 1440x1000/1024x1366/390x844 layouts, keyboard-only completion, focus restoration, 200-percent-equivalent reflow, reduced motion, no overflow, and principal-route axe passed |
| `node scripts/verify-gate2-screenshots.mjs`        | Verified 36 exact captures, dimensions, SHA-256 values, checkpoint SHA, and zero external requests                                                                                                 |
| Lead and independent visual score                  | 95/100; every authority-rubric category at least 90 percent; zero critical accessibility defects and zero anti-reference violations                                                                |
| `npm audit --audit-level=high`                     | Exit 0; 0 vulnerabilities                                                                                                                                                                          |
| `openspec validate claros-reconstruction --strict` | Exit 0; change valid                                                                                                                                                                               |
| Authority SHA-256 checks                           | All three exact expected hashes still match                                                                                                                                                        |
| `git diff --check`                                 | Exit 0; no authored whitespace errors                                                                                                                                                              |

The first expanded Playwright replay exposed five test-harness defects: lazy
cold-start timing, two ambiguous text locators, an assertion applied to the
guided path instead of only direct typing, and a DOM-order check made before the
workspace mounted. Each was corrected without weakening product assertions;
the focused five-test replay and the subsequent complete 22-test replay passed.
The final visual review is recorded in
`artifacts/v2/gate2-visual-scorecard.md`.

## Fresh Gate 3 verification — 2026-09-04

The complete record is in `artifacts/v2/gate3/verification.md` and is bound to
accepted clean checkpoint `88cda664f55abf698a1d56567e814e024708ad0a`.

| Command/evidence                   | Result                                                                                                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run ci` under Node `v22.22.0` | Exit 0; format, lint, typecheck, dependency/license contract, OpenAPI drift, 73/73 Vitest tests, Storybook build and axe sweep, production build, and bundle closure passed |
| `npm run test:e2e`                 | Exit 0; 22/22 fixture Chromium flows passed                                                                                                                                 |
| `npm run test:e2e:gate3`           | Exit 0; the real FastAPI typed/partial-export flow survived a service restart                                                                                               |
| Gate-3-only pytest                 | 392 tracked tests passed with 92-percent branch coverage; 23 third-party deprecation warnings                                                                               |
| Focused reviewer replay            | 90 API/storage/PDF/security tests passed; all critical code findings were fixed                                                                                             |
| Ruff format/lint                   | All tracked Python sources formatted correctly and lint-clean                                                                                                               |
| Dependency audits                  | `npm audit --audit-level=high` reported 0 vulnerabilities; `pip-audit -r requirements-server.txt` found none                                                                |
| Terraform                          | Format, lockfile-readonly initialization, and validation passed with Terraform 1.15.2 and Google provider 7.46.0                                                            |
| Document corpus                    | Twelve checksum-pinned categories plus all required negative classes passed determinism, exact-text, placement, and failure-code checks                                     |
| Manual PDF reopening               | The same SHA-bound inline/appendix export opened correctly in Chrome and Adobe Acrobat 64-bit with source content intact and no appendix truncation                         |
| Authority/OpenSpec/whitespace      | Authority hashes matched; strict OpenSpec and diff checks passed                                                                                                            |
| Production container               | GitHub Ubuntu run `33941739290` passed for clean head `88cda66`; artifact `9962065063` retains both privacy-checked logs and parser-reopened inline/appendix PDFs           |
| Remote source build                | Cloud Build `8bcf24be-5be9-4e81-a8e5-fc2947d39754` built the clean committed archive and published immutable digest `sha256:b4058b7b…d5b66`                                 |
| Live GCS/Cloud Run replacement     | Revisions `claros-00074-kxl` → `claros-00075-xtv` passed live GCS persistence, ownership isolation, forged-proxy identity, inline/appendix export, and parser reopen        |
| Deployed privacy                   | 69 Cloud Logging entries scanned with zero worksheet, answer, cookie/token, or credential canary matches                                                                    |

The implementation reserves 30 seconds beneath the 300-second Cloud Run
request ceiling, bounds GCS RPCs and retries, persists owner-recoverable
analysis failures, and lets unsafe higher-priority placement candidates fall
through deterministically to lower-priority classes. These fixes were included
before the checkpoint and exercised through both remote acceptance paths.

## Gate 0 evidence commands

Run from the repository root in PowerShell and retain the complete output:

```powershell
git branch --show-current
git rev-parse HEAD
Get-FileHash -Algorithm SHA256 .\CLAROS_V2_SOL_ULTRA_EXECUTION_PRD.md
Get-FileHash -Algorithm SHA256 .\CLAROS_V2_PRODUCT_CONTRACT.md
Get-FileHash -Algorithm SHA256 .\CLAROS_V2_DESIGN.md
npm ci
npm run ci
npm run build-storybook
npm run test:e2e
npm audit --audit-level=high
openspec validate claros-reconstruction --strict
Get-ChildItem -Recurse .\test-results -Filter *.png
git diff -- package.json package-lock.json src server
git status --short -- package.json package-lock.json src server
git diff --check
git status --short
```

Expected authority hashes are listed in `BASELINE_AUDIT.md`. The dependency and
production-source diff must be empty for Gate 0. Any HIGH/CRITICAL runtime
finding or unavailable npm audit keeps Gate 1 blocked.

## Delivery gates

| Gate | Deliverable                                                                            | Blocking evidence                                                                                             | State                        |
| ---- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| 0    | Authorities, synthesis, in-place OpenSpec, dependency/ownership plan                   | Hashes, baseline regressions, npm audit, strict OpenSpec, clean production diff, planning commit              | Passed at `0c15404`          |
| 1    | Untitled foundation, V2 routes/providers, scoped legacy, authentic EmbedPDF spike, MSW | Build/tests, route and keyboard smoke, CSP/WASM/worker proof, no PDF request from `/`                         | Passed at `59cbc50`          |
| 2    | Fixture-complete V2 UI and fake Realtime                                               | Unit/component/Storybook/Playwright/axe, keyboard/focus/zoom/motion, full screenshot matrix, visual score ≥90 | Passed at `0723303` — 95/100 |
| 3    | FastAPI, GCS adapters, physical IR, placement/export, gold corpus                      | Python/API/PDF integration, deterministic IR, exact Unicode, immutable source, container/revision smoke       | Passed at `88cda66`          |
| 4    | Responses semantic mapping and rephrase                                                | Recorded/live corpus evaluation, zero invalid IDs, exact reconstruction, safe failure and provenance          | Passed at `976e176`          |
| 5    | One adaptive Realtime conversation                                                     | Fake browser suite and manual live voice/recovery/security evidence                                           | In progress — 11/13 tasks    |
| 6    | Cutover, hardening, deployment                                                         | Full accumulated CI/security/a11y/visual/performance/staging evidence                                         | Not started                  |
| 7    | Repeatable demo and release bundle                                                     | Clean-browser replay, final PDF, deployed smoke, honest submission copy, complete `artifacts/v2`              | Not started                  |

## Gate command contract

Gate 1 adds stable scripts for frontend format, lint, typecheck, unit,
Storybook/browser, build, E2E, accessibility, visual, and API-drift checks.
Gate 3 adds Ruff, pytest contract/PDF/integration coverage, pip-audit, corpus,
container, and `/health` smoke commands. Each later gate reruns every applicable
earlier command against one recorded commit SHA. Manual Chrome/Adobe Reader,
keyboard, live voice, visual, and deployment checks are retained as signed
checklist evidence rather than represented as automation.

## Fixed defaults

- P0 document limits: 10 MiB, 1–8 pages, at most 40 questions.
- Export answer floor: 10pt; fit begins at 12pt.
- Anonymous assignment TTL: 24 hours absolute.
- Review token TTL: 10 minutes, single-mutation with idempotent exact replay.
- P0 processing: bounded synchronous analysis/export with reload-safe status.
- Source delivery: same-origin, authorized, Range-capable proxy.
- Production: one stateless FastAPI/Vite Cloud Run service plus private GCS.
- Health endpoint: `/health`.
- Realtime default: `gpt-realtime-2.1`; semantic default is selected by the
  Gate 4 corpus benchmark.
- P0 restoration: owning browser session only; cross-device/shareable resume
  remains P1.

## Gate 0 exit statement

Gate 0 passed after every checklist item produced objective evidence and the
planning-only checkpoint changed no dependency, production-source, generated
UI, or runtime file. `DECISIONS.md` freezes the Gate 1 interfaces and
`RISKS.md` supplies its stop conditions.

## Gate 1 exit statement

Gate 1 passed at content checkpoint
`59cbc509650cc4a65b139a7db23012ead74efb3c`. The Node 22 clean-install evidence,
full automated checks, real PDF browser evidence, dependency/license audit, and
independent review have no blocking finding. The only retained concerns are
explicit upgrade/cutover risks in `RISKS.md`; they do not weaken any Gate 1
acceptance invariant.

## Gate 2 exit statement

Gate 2 passed at content checkpoint
`0723303ef718bb28594d519da31ec0a55226fa45`. The fixture-complete workflow,
authentic source and completed-copy views, responsive matrix, full automated
checks, and independent 95/100 review have no blocking finding. This checkpoint
does not claim durable assignment truth, dynamic PDF placement/export, a live
semantic model, or live WebRTC; those boundaries remain blocked behind Gates
3–5 exactly as required.

## Gate 3 exit statement

Gate 3 passed at accepted clean checkpoint
`88cda664f55abf698a1d56567e814e024708ad0a`. Local contract, storage,
document, browser, security, corpus, audit, and manual PDF evidence passed. The
head-associated Ubuntu workflow tested the immutable pull-request merge
revision containing that checkpoint, built and restarted the production
container, and retained privacy-checked logs plus reopened PDFs. The
owner-authorized Cloud Run deployment then proved GCS persistence across
revision replacement, cross-owner denial, managed-proxy identity behavior,
exact digest use, and live browser export/reopen. Windows Docker Desktop is
optional and was not used as acceptance evidence. Tasks 3.8 and 3.9 are
complete; later gates remain unimplemented and must preserve the frozen Gate 3
contracts.

## Gate 4 exit statement

Gate 4 passed at reviewed evidence checkpoint
`976e176ea0fe828147684757ae7cf07e37a1e175`. The required bounded live selection
stopped at Luna after three complete 11/11 runs with zero invalid IDs and a
7,142 ms p95, and the live rephrase check passed. The report is reproducibly
bound to clean source checkpoint `121287e`, verified corpus bytes, prompt, and
schemas. Independent review found no remaining critical issue. No credential,
raw provider payload, or generated answer text is committed.
