# Claros Build Week Execution Plan

> **Historical document (Build Week / contest-era plan).** This is **not** the
> current Claros product roadmap or runtime architecture. OpenAI/GPT-5.6 /
> OpenAI Realtime targets below describe a superseded candidate path. Current
> product: Gemini + deterministic confirmation/write ownership —
> [`ARCHITECTURE.md`](ARCHITECTURE.md), [`CLAROS_REVAMP_ROADMAP.md`](CLAROS_REVAMP_ROADMAP.md),
> and Stage records in [`BUILD_WEEK_DELTA.md`](BUILD_WEEK_DELTA.md).

**Status:** historical planning document (do not execute as present-tense work)
**Worktree:** `C:\Users\Chimdumebi\Claros`
**Baseline branch at plan time:** `feat/claros-session2-rebuild` @ `e232daf29330ce3a198659c5b9709df95ea5bafa`
**Remote main at plan time:** `3e356976b1ca5b097efd3d7330803e9e4818d37f`
**Contest start (owner-confirmed):** `2026-07-13T09:00:00-07:00` / `2026-07-13T11:00:00-05:00`

## Product direction

Claros is a human-free worksheet-understanding and tutoring system, except for one intentional human control:

**The student must explicitly approve their final answer before Claros writes it into the worksheet.**

No teacher, administrator, annotator, or developer is required to prepare a worksheet during normal product use.

There is **no human adjudication** of document labels. Evaluation uses an **AI-adjudicated silver benchmark** only. Never call those labels human gold, ground truth, expert labels, or human-verified labels.

Architectural principle:

`Human-free operation, AI-adjudicated evaluation, student-controlled actions.`

### Final runtime architecture

1. User uploads a supported PDF.
2. Deterministic code extracts page images, source blocks, geometry, reading-order evidence, and physical response candidates.
3. GPT-5.6 interprets the page using image evidence and the closed-world physical intermediate representation.
4. GPT-5.6 identifies page roles, student tasks, compound structures, parent/subpart relationships, and links tasks to supplied response candidates.
5. Deterministic validators reject unsupported IDs, invented text, invented coordinates, invalid relationships, and unsafe placements.
6. Claros automatically uses a verified physical answer region when safe.
7. Claros automatically uses a side-panel answer when physical placement is uncertain or unsafe.
8. OpenAI Realtime handles speech input, speech output, transcript delivery, and interruption.
9. GPT-5.6 handles structured tutoring decisions and grounded candidate-answer extraction.
10. The student reviews and confirms the proposed answer.
11. Deterministic session and write-token code authorizes the action.
12. Deterministic PDF code writes and exports the answer.

## Non-negotiable authority boundaries

GPT-5.6 may own:

- page-role classification
- task discovery
- task grouping
- parent and subpart relationships
- source-block selection
- response-candidate selection
- prompt reconstruction from cited blocks
- answer-type classification
- tutoring-plan generation
- tutoring-turn decisions
- grounded candidate-answer extraction
- decisions to guide, hint, clarify, propose an answer, or request confirmation

OpenAI Realtime may own:

- speech recognition
- speech output
- turn detection
- interruption
- realtime conversational transport
- transcript events

GPT-5.6 and OpenAI Realtime must **not** own:

- source block IDs
- PDF coordinates
- physical response-candidate generation
- final coordinate validation
- student confirmation
- write-token issuance
- assignment authorization
- export authorization
- PDF modification
- overflow handling
- side-panel rendering
- security decisions

Deterministic application code retains those responsibilities.

## Current repository facts

Treat the local worktree as the source of truth.

Known local state:

- substantial modified tracked files
- substantial untracked document-understanding work
- existing 20-PDF, 109-page local corpus (outside repo)
- existing 17-page evaluation pilot
- **no human gold labels and no human adjudication**
- default legacy parser
- untracked hybrid document pipeline
- Gemini Live as current voice provider
- deterministic confirmation and write-token path
- multiple parser and exporter implementations
- stale and contradictory documentation

Important local candidate files:

- `document_model.py`
- `document_pipeline.py`
- `semantic_classifier.py`
- `review_service.py`
- `evaluation/`
- `output/`
- PaddleOCR requirement files
- PDF benchmark scripts
- pilot schemas and physical-input caches
- `docs/CLAROS_OPENAI_AUDIT_HANDOFF.md`

Read the complete audit handoff before changing code.

## Operating rules

Do not discard local work.

Do not run:

- `git reset --hard`
- `git clean`
- destructive checkout commands
- broad file deletions
- mass formatting unrelated to the work
- expensive full-corpus OCR unless specifically required
- cloud deployments before local verification
- provider calls before schemas, validators, mocks, and cost controls exist

Do not commit:

- `.env`
- API keys
- credentials
- private user documents
- external corpus PDFs without explicit rights confirmation
- large generated output directories
- raw provider secrets
- local browser profiles
- machine-specific paths as runtime configuration

Do not expose secret values in logs, reports, tests, screenshots, commits, or final output.

Do not stop merely because a credential is unavailable. Implement the adapter, mocks, tests, configuration, and documentation, then continue with all offline work. Record unavoidable credential-dependent validation separately.

### Commit policy

- Prefer owner-approved commits, or commit only after an explicit allowlist of paths for that phase.
- Suggested commit messages below are boundaries, not autonomous mandates when the staging set is ambiguous.
- Never stage secrets, corpora, or bulk `output/`.

### Metric language for silver labels

Because there is no human adjudication:

- Primary metrics are **agreement**, **adjudication rate**, **abstention rate**, **validator catch rate**, and **unsafe automatic-placement rate**.
- Do **not** present silver-vs-compiler scores as absolute accuracy.
- If reporting task precision/recall/F1, label them explicitly as:

  `silver-relative agreement / provisional F1 against AI-adjudicated silver`

  Never as accuracy, correctness, or human-validated quality.

## MVP cut line

Ship this even if later phases fail:

1. Phase 0 preserve/classify worktree
2. Phase 2 P0/P1 security and session defects
3. Thin physical IR + closed-world GPT-5.6 compiler vertical slice
4. AI-adjudicated silver benchmark on the 17-page pilot
5. Honest docs + demo on the strongest verified path

If OpenAI Realtime is unstable, keep Gemini Live for the demo and submit the OpenAI document-compiler story. Do not claim an incomplete voice migration.

## Agent structure

Primary coordinator owns final decisions and integration.

Use isolated subagents when useful; avoid parallel edits to the same files.

### Repository steward

- inventory the dirty worktree
- classify tracked and untracked files
- identify private or generated materials
- preserve valuable candidate code
- establish branch and commit boundaries
- reconcile canonical and dormant implementations

### Security red-team agent

- reproduce assignment/session/export defects
- challenge authorization boundaries
- test stale state
- inspect secret configuration
- inspect public mutation routes
- inspect export bypasses
- inspect abuse and retention risks

### Document-semantics agents (silver only; no human labels)

Isolated agents for the silver benchmark:

- task annotator
- conservative false-positive annotator
- structure and placement annotator
- adversarial critic
- AI adjudicator (may abstain)

Initial annotators must not see one another’s outputs.

### Compiler agent

- define the physical IR
- define GPT-5.6 strict schemas
- implement closed-world compilation
- implement validation and materialization
- integrate results into the product

### Voice migration agent

- isolate the current voice-provider interface
- add an OpenAI Realtime adapter
- migrate browser audio and transcript events
- preserve interruption and typed fallback
- remove Gemini only after verification

### QA agent

- browser tests
- provider mocks
- document-evaluation tests
- PDF visual checks
- second-run reliability
- deployment checks
- accessibility checks

### Documentation and provenance agent

- Build Week delta
- architecture documentation
- README truth
- deployment documentation
- Codex provenance
- demo script
- Era framing
- deletion of stale roadmap only after migration

Every subagent must return evidence, not only recommendations.

Red-team checkpoints (required): after Phases 2, 5, 7, and 9.

## Phase 0: Preserve and classify the local worktree

Before editing application code:

1. Run and record (bounded; do not dump unbounded full history into context):

```bash
git status --short
git branch --all --verbose
git log --graph --decorate --oneline --all -50
git rev-list -1 --before="2026-07-13T09:00:00-07:00" origin/main
git ls-files --others --exclude-standard
git diff --stat
```

2. Create a complete file classification table for important paths:

- production source
- candidate source worth integrating
- test fixture
- evaluation source
- generated output
- private/local corpus
- documentation
- obsolete code
- unresolved

3. Do not stash or reset the existing work.

4. Create or switch to:

`build-week/claros-openai`

without losing changes.

5. Update `.gitignore` carefully for:

- generated benchmark output
- local corpora
- provider caches
- browser profiles
- private PDF folders
- secrets
- temporary OCR artifacts

6. Preserve source code, schemas, evaluation code, and reproducible small fixtures.

7. Do not commit external PDF corpora until rights and privacy are verified.

8. Create:

`docs/LOCAL_WORKTREE_INVENTORY.md`

Acceptance criteria:

- no local work lost
- no secret values exposed
- every important untracked file classified
- candidate document work is understandable before integration
- branch exists
- repository status is documented

Suggested commit:

`chore(repo): preserve and classify local Claros work`

## Phase 1: Establish Build Week provenance and repository instructions

Create:

- `AGENTS.md`
- `docs/BUILD_WEEK_DELTA.md`
- `docs/BUILD_WEEK_ROADMAP.md`
- `docs/ARCHITECTURE.md`

Using the owner-confirmed start timestamp above, determine the last commit before that timestamp and record:

- exact baseline SHA
- baseline functionality
- post-baseline commits
- authors and co-authors
- Codex-attributable work
- Cursor-attributable work
- manual or unresolved provenance
- current primary Codex session
- future primary session ID after `/feedback` is run

Do not claim all contest-period work was produced by Codex. Do not fabricate session IDs.

`AGENTS.md` must define:

- product mission
- supported document boundary
- no invented coordinates
- no invented source text
- no write without student confirmation
- side-panel safety behavior
- deterministic authority boundaries
- required test commands
- documentation update requirements
- privacy rules
- benchmark naming rules (silver only; no human-gold language)
- commit expectations
- Build Week provenance rules

Acceptance criteria:

- exact baseline recorded
- no unsupported provenance claims
- architecture boundaries are explicit
- durable repository instructions exist

Suggested commit:

`docs(build-week): establish baseline, architecture, and agent rules`

## Phase 2: Repair existing P0 and P1 defects

Fix these before model migration.

### Assignment-scoped browser reset

Current replacement behavior can retain old `sessionId`, `sessionSecret`, conversation, confirmation state, write tokens, export voice dedupe, and sessionStorage values.

Create a canonical function such as:

`clearAssignmentSessionState()`

Use it whenever:

- replacing a worksheet
- loading a new worksheet
- resetting the workspace
- detecting an assignment mismatch
- restoring an expired or invalid session

Regression scenario:

1. Upload worksheet A.
2. Start a session.
3. Confirm or write an answer.
4. Replace worksheet A with worksheet B.
5. Start or confirm on B.
6. Verify no A state, secret, conversation, token, or export dedupe survives.

### Assignment authorization

Public UUID-based routes may permit unauthorized review, mutation, deletion, export, and preview access.

Implement an owner capability model for a no-account prototype:

- generate a high-entropy assignment capability secret on upload
- return it only to the creating browser
- store only its keyed hash server-side
- require it for assignment mutation, export, delete, review, and sensitive page access
- store it in assignment-scoped sessionStorage
- never place it in URLs
- use constant-time comparison
- rotate or destroy it when the assignment expires or is deleted

Public landing assets and health routes remain unauthenticated.

### Export authorization and confirmation

Prevent callers from bypassing student confirmation by posting arbitrary answer text directly to `/export`.

Canonical behavior:

- persist confirmed/written answer state server-side
- export only server-authorized written answers
- or require a valid assignment capability plus session confirmation evidence for every exported answer
- reject unconfirmed or mismatched text
- reject arbitrary client-supplied answer regions unless validated and persisted through the canonical review/correction path

### HMAC secret

Remove fixed production fallback behavior.

- development may generate or clearly warn about an ephemeral secret
- production must fail startup when `SESSION_HMAC_SECRET` is absent
- deployment workflow must inject the secret
- `.env.example` and deployment docs must list only the variable name and instructions

### Retention and deletion

Clarify logical versus physical retention.

Implement or document:

- assignment expiration
- session expiration
- delete behavior
- GCS lifecycle requirement
- cleanup command or scheduled cleanup path
- no unsupported automatic-deletion claim

### Abuse controls

Add reasonable prototype safeguards:

- request body and page limits already present
- per-IP or capability-aware rate limits for expensive routes
- upload concurrency limits
- provider-call limits
- maximum compilation pages
- maximum model-input size
- maximum retry count
- cost and latency metrics without content logging

### Export overflow

Remove silent or ignored overflow.

The exporter must:

- paginate side-panel answers when needed
- detect textbox insertion failure
- never silently truncate confirmed text
- return explicit affected task IDs on unrecoverable failure
- include regression tests for long answers

Acceptance criteria:

- second worksheet in the same tab works
- arbitrary export bypass is rejected
- unauthorized mutation is rejected
- production startup rejects missing HMAC secret
- confirmed answer text is not silently truncated
- all new defects have regression tests

Suggested commits:

- `fix(session): isolate assignment-scoped browser state`
- `feat(security): add assignment capability authorization`
- `fix(export): require authorized confirmed answers`
- `fix(config): require production session secret`
- `fix(pdf): eliminate silent side-panel overflow`

## Phase 3: Canonicalize parser, document IR, review, and exporter paths

Inspect and decide the fate of:

- `parser.py`
- `parser_layout.py`
- `document_model.py`
- `document_pipeline.py`
- `semantic_classifier.py`
- `review_service.py`
- `manifest.py`
- `assignment_service.py`
- `exporter.py`
- `ocr_adapter.py`
- `schemas.py`
- all parser and PDF evaluation scripts

Create a production-path table before deletion.

### Physical document IR

Create one canonical versioned physical intermediate representation containing:

- document ID
- parser version
- source hash
- pages
- page image reference or reproducible render metadata
- page width and height in PDF points
- stable source block IDs
- block text
- block bounding boxes
- reading order
- physical source type
- physical confidence
- response candidates
- candidate kind
- candidate geometry
- candidate physical-safety status
- candidate provenance
- compiler result
- tasks
- parent and subpart relationships
- model and prompt version
- validation result
- side-panel routing reason
- optional user-correction provenance
- final write region
- export provenance

Canonical coordinate system:

- PDF points
- top-left origin
- `[x0, y0, x1, y1]`

Normalize only at the frontend boundary when necessary.

### Remove duplicate semantics

Choose one canonical:

- parser entrypoint
- manifest builder
- response-candidate representation
- review/correction representation
- exporter
- overflow strategy

Retain old code temporarily only for evaluation comparison. Mark explicitly as baseline evaluator only, compatibility shim, or deprecated pending removal.

### Runtime human-free behavior

Do not require teacher review.

When semantic or placement confidence is insufficient:

- route answer to side panel automatically
- mark the task as uncertain in the UI
- allow optional user correction
- never block normal use waiting for an external reviewer

Optional user correction may:

- select the correct task
- select an existing safe response candidate
- move to side panel

Do not permit arbitrary unsafe coordinates without deterministic validation.

Prefer a thin vertical slice first (one pilot page end-to-end), then broaden canonicalize after the compiler proves itself.

Acceptance criteria:

- one canonical physical IR
- one canonical parser orchestration path
- one canonical exporter
- no dead layout override contract in the active API
- uncertain tasks work without teacher intervention
- legacy parser remains runnable only for baseline comparison
- unit and migration tests pass

Suggested commits:

- `refactor(document): establish canonical physical IR`
- `refactor(parser): unify production document pipeline`
- `refactor(export): canonicalize placement and side-panel behavior`
- `feat(document): add human-free uncertainty routing`

## Phase 4: Build the AI-adjudicated silver benchmark

Use the existing 17-page pilot.

Do **not** wait for human annotation or human adjudication.

Create:

```text
evaluation/pdf_silver_benchmark/
  README.md
  benchmark_manifest.json
  schemas/
  prompts/
  physical_inputs/
  agent_outputs/
    task_annotator/
    conservative_annotator/
    structure_annotator/
  critiques/
  adjudications/
  labels/
    accepted/
    adjudicated/
    challenge/
  validators/
  tests/
  reports/
  evaluate.py
  freeze.py
```

Do not copy external PDFs into the repository without permission.

Reference local source files using content hash, page number, local configuration placeholder, and reproducible rendering instructions.

### Independent annotation agents

For every page run isolated:

#### Agent A: Task annotator

Identify student tasks, source block IDs, groupings, parents, subparts, and likely response candidates.

#### Agent B: Conservative annotator

Minimize false positives. Reject directions, examples, answer keys, teacher content, rubrics, standards, references, and decorative numbering.

#### Agent C: Structure and placement annotator

Focus on compound structures, tables, diagrams, response candidates, automatic placement safety, and side-panel routing.

#### Agent D: Red-team critic

Review all three results and aggressively search for:

- over-splitting
- under-splitting
- duplicated tasks
- swallowed subparts
- invented IDs
- unsupported text
- teacher-content contamination
- unsafe candidate selection
- incorrect page roles
- invalid parent graphs
- cross-page mistakes
- ambiguous response links

#### Agent E: AI adjudicator

Resolve disagreements with explicit page evidence. May abstain. There is no human override step.

### Deterministic benchmark validators

Reject or quarantine:

- unknown block IDs
- unknown response-candidate IDs
- invented coordinates
- task text not reconstructible from blocks
- duplicate task keys
- parent cycles
- invalid parent references
- automatic writes on teacher or answer-key pages
- unsafe automatic response candidates
- incompatible cross-page relationships
- overlapping exclusive response assignments
- unresolved pages marked automatically writable

### Benchmark partitions

- `accepted silver`
- `adjudicated silver`
- `challenge set`

Do not discard disagreements.

### Benchmark freeze

Before evaluating the compiler:

- hash page images
- hash physical inputs
- hash schemas
- hash prompts
- hash labels
- hash benchmark manifest
- freeze the benchmark version
- store predictions separately from labels
- require a version increment to change reference labels

### Metrics

Report:

- page-role agreement
- task-count agreement
- exact task-boundary agreement
- grouping agreement
- parent/subpart agreement
- response-link agreement
- automatic versus side-panel agreement
- invalid-ID rate
- adjudication rate
- abstention rate
- deterministic validation failures

These are agreement / integrity metrics, not human accuracy.

Acceptance criteria:

- all available 17 pages processed
- every label validates or enters challenge set
- benchmark frozen
- reference labels separated from predictions
- prompts, schemas, costs, hashes, and model configurations recorded
- tests cover invalid labels and freeze behavior
- README explicitly states no human adjudication

Suggested commits:

- `feat(eval): add multi-agent PDF silver benchmark`
- `test(eval): validate benchmark integrity and freezing`
- `docs(eval): document silver-label limitations`

## Phase 5: Implement the GPT-5.6 closed-world document compiler

Create a provider-neutral interface.

Suggested structure:

```text
providers/
  semantic_compiler.py
  openai_semantic_compiler.py

document/
  models.py
  physical.py
  candidates.py
  compiler.py
  validate.py
  materialize.py
```

Adapt existing local files rather than duplicating them unnecessarily.

### Compiler input

GPT-5.6 receives:

- page image
- page role options
- stable source block inventory
- block text
- block geometry
- reading-order metadata
- supplied response candidates
- candidate kinds and safety metadata
- strict instructions
- no hidden compiler prediction from another system

### Compiler output

Strict structured output only:

- page role
- selected source block IDs
- rejected block IDs
- task keys
- prompt block IDs
- parent task keys
- subpart labels
- response-candidate IDs
- answer type
- placement recommendation
- reason codes
- uncertainty status

The model may not return invented prompt text, invented source text, coordinates, arbitrary regions, write authorization, confirmed answers, or export instructions.

### Deterministic materialization

Code must:

- verify all IDs exist
- reconstruct prompt text from selected blocks
- validate reading-order consistency
- validate parent graph
- validate response-candidate safety
- derive final geometry only from selected candidates
- route uncertain tasks to side panel
- record model, schema, prompt, input hash, latency, and cost
- avoid logging worksheet content by default

### Retry policy

Bounded retries only for invalid schema, unknown IDs, incomplete partition, or invalid parent graph.

Do not keep retrying semantic disagreement.

After bounded failure: mark task or page unresolved, use safe fallback, keep product usable.

### Evaluation

Evaluate:

1. legacy parser
2. existing local hybrid pipeline
3. GPT-5.6 compiler

Against accepted silver and adjudicated silver. Report separately. Do not score challenge pages as ordinary reference cases.

Measure:

- silver-relative task precision / recall / F1 (explicitly labeled provisional)
- page-role agreement
- grouping agreement
- parent/subpart agreement
- source-block selection agreement
- response-link agreement
- unsafe automatic-placement rate
- side-panel routing agreement
- abstention behavior
- latency
- API cost

### Promotion criteria

GPT-5.6 becomes the default semantic compiler only when:

- no invented IDs survive validation
- unsafe automatic-placement rate is zero on accepted silver
- it improves silver-relative task F1 **or** substantially improves false-positive and side-panel safety behavior over legacy
- all failures degrade safely
- latency is acceptable for the demo
- cost is recorded and bounded
- the product remains functional when the compiler fails

Acceptance criteria:

- one page works end to end
- all 17 pilot pages evaluated where inputs exist
- compiler is closed-world
- validator catches invalid model output
- side-panel fallback works
- reports are reproducible

Suggested commits:

- `feat(openai): add GPT-5.6 closed-world document compiler`
- `feat(document): materialize validated semantic task graphs`
- `test(openai): add compiler schema and adversarial validation`
- `eval(document): compare legacy, hybrid, and GPT-5.6`

## Phase 6: Replace regex tutoring decisions with GPT-5.6

Create a provider-neutral tutoring decision interface.

Suggested structured actions:

- `ask_guiding_question`
- `offer_small_hint`
- `clarify_task`
- `identify_active_task`
- `propose_student_answer`
- `request_confirmation`
- `refuse_early_write`
- `acknowledge_interruption`
- `end_session`

Input should include active task ID, task text reconstructed from document blocks, tutoring plan, bounded recent transcript turns, confirmed state, candidate-answer state, and explicit product rules.

Output should include action, active task ID, short spoken reply, candidate answer or null, whether the student appears to have stated a final answer, evidence turn IDs, and reason code.

### Grounded answer extraction

The model may propose a candidate answer only from the student’s transcript.

Preserve original capitalization, punctuation, code identifiers, mathematical symbols, and quoted language.

Do not use normalized text as the stored candidate answer. Normalized text may remain for deterministic fallback intent matching.

### Student confirmation

The model can request confirmation. It cannot confirm for the student.

UI must present proposed task, proposed answer, edit, reject, and confirm.

Only confirmation triggers server-side write authorization.

### Tutoring plans

Generate a bounded plan for each task: concept, expected response form, prerequisite, likely misconception, three-level hint ladder, prohibited direct-answer behavior, and evidence required before proposing a final answer.

Acceptance criteria:

- uncommon natural answer phrasings work
- transcript capitalization is preserved
- no model action writes directly
- exact structured actions are testable
- deterministic confirmation remains authoritative
- scripted tutoring evals pass

Suggested commits:

- `feat(tutoring): add GPT-5.6 structured turn decisions`
- `feat(tutoring): preserve grounded raw candidate answers`
- `test(tutoring): add adversarial decision cases`

## Phase 7: Replace Gemini Live with OpenAI Realtime

Do this only after the document compiler and tutoring decision interface are stable.

Create a provider-neutral browser voice adapter before replacing the provider.

Suggested frontend boundary:

```text
frontend/voice/
  adapter.js
  openai-realtime.js
  audio.js
  transcript.js
```

Suggested backend boundary:

```text
providers/
  realtime.py
  openai_realtime.py
```

Configurable environment variables:

- `OPENAI_API_KEY`
- `OPENAI_REASONING_MODEL`
- `OPENAI_REALTIME_MODEL`
- `OPENAI_REALTIME_VOICE`

Do not hard-code model identifiers outside configuration defaults.

### Required behavior

- explicit microphone permission
- browser-safe ephemeral session creation
- transcript delivery
- spoken output
- interruption
- stopping queued playback
- reconnect behavior
- provider failure fallback
- typed fallback
- no API key exposure in the browser
- no transcript content in operational logs
- bounded session duration
- assignment-scoped conversation state

### Provider mocks

Before live testing, create deterministic fixtures for transcript deltas, cumulative transcripts, completed user turns, assistant text/audio, interruption, disconnect, invalid session, token expiration, reconnect, and duplicated events.

### Migration

Once the OpenAI path passes:

- remove browser `GoogleGenAI`
- remove `frontend/genai.bundle.js`
- remove `build-genai.mjs`
- remove `@google/genai`
- remove `gemini_service.py`
- remove Gemini configuration, routes, deployment secrets, documentation, tests, and Gemini-specific prompts

Do not retain Gemini as an active fallback in final mainline code. Keep rollback history in Git.

If Realtime cannot stabilize before submission: keep migration work on the branch and submit the strongest verified OpenAI document-compiler workflow. Do not claim the incomplete voice migration.

Acceptance criteria:

- three consecutive live voice sessions complete
- interruption works
- transcript handling works
- typed fallback works
- second worksheet works in the same tab
- provider failure does not lose confirmed answers
- no Gemini dependency remains
- all documentation and deployment config use OpenAI

Suggested commits:

- `refactor(voice): introduce provider-neutral realtime adapter`
- `feat(openai): migrate voice sessions to OpenAI Realtime`
- `test(voice): add realtime event and recovery fixtures`
- `chore(gemini): remove Gemini runtime and build dependencies`

## Phase 8: Browser, PDF, security, and accessibility verification

Add a real browser test harness.

### Core flow

load landing → open app → upload sample → compile document → select task → type answer → confirm → write → export → inspect PDF → repeat with second worksheet

### Voice flow

microphone allowed/denied, provider unavailable/disconnect/reconnect, interrupt, transcript partials/final, candidate answer, edit, reject, confirm, export

### Document flow

explicit numbered questions, compound labels, parent/subparts, two columns, table, mixed teacher/student content, no safe physical answer region, side-panel routing, scanned page using GPT vision, unsupported page, long answer overflow, multi-page export

### Security flow

missing/wrong/stale capability, assignment mismatch, export bypass, mutation bypass, expired session, reused write token, concurrent confirmation/write, rate-limit response

### Accessibility

keyboard-only navigation, visible focus, screen-reader labels, status announcements, confirmation dialog semantics, 200 percent zoom, reduced motion, mobile layout, no microphone requirement, no drag-only correction mechanism

Acceptance criteria:

- all deterministic tests pass
- browser suite passes
- exported PDF retains original pages
- no silent truncation
- no unauthorized mutation
- accessibility failures are documented and repaired where critical
- live provider tests are recorded separately from mocked CI tests

Suggested commits:

- `test(browser): add complete Claros workflow coverage`
- `test(security): add assignment capability and export abuse cases`
- `test(pdf): add visual placement and overflow regression`
- `fix(a11y): resolve critical workspace accessibility defects`

## Phase 9: Deployment migration and production verification

Update:

- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `Dockerfile`
- dependency files
- `.env.example`
- `DEPLOY.md`
- `docs/github-actions-deploy.md`

Production deployment must include OpenAI key secret, reasoning model configuration, Realtime model configuration (if Realtime shipped), session HMAC secret, GCS configuration, production environment flag, bounded instance/concurrency settings, lifecycle-policy documentation, and post-deploy checks.

Do not print secret values.

Post-deploy checks: `/health`, `/`, `/app`, static assets, upload, session start, authorized write, authorized export, second worksheet, provider session creation, typed fallback.

Do not claim production verification when only local tests ran.

Acceptance criteria:

- Docker build passes
- CI passes
- deploy workflow matches the verified provider path
- production secret requirements are explicit
- post-deploy smoke commands are reproducible
- actual deployment status is honestly recorded

Suggested commit:

`ci(openai): migrate build and deployment to OpenAI runtime`

## Phase 10: Documentation migration and stale roadmap deletion

Reconcile:

- `README.md`
- `PRODUCT.md`
- `DESIGN.md`
- `LAYOUT.md`
- `DEPLOY.md`
- `docs/CLAROS_AUDIT.md`
- `docs/CLAROS_DAILY_PROGRESS.md`
- `docs/github-actions-deploy.md`
- `.env.example`
- workflow comments
- product copy
- current limitations

Public claims must match verified code.

README must clearly explain what Claros does, who it serves, supported document boundary, GPT-5.6 document compiler, voice provider actually shipped, student confirmation, deterministic write authorization, safe physical placement, automatic side-panel fallback, evaluation methodology, silver benchmark limitation (**no human adjudication**), privacy/retention limitations, local setup, test commands, deployment, and Build Week delta.

Migrate useful evidence from the old roadmap into Build Week docs, architecture docs, and evaluation reports.

Then delete `docs/CLAROS_DAILY_PROGRESS.md` only after useful evidence is migrated, repository references are repaired, current documentation is authoritative, and Git history preserves the old file.

Suggested commits:

- `docs(openai): reconcile Claros architecture and evaluation`
- `docs(build-week): finalize contest delta and evidence`
- `chore(docs): remove stale daily progress roadmap`

## Phase 11: Build Week and Era deliverables

Create:

- `docs/BUILD_WEEK_SUBMISSION.md`
- `docs/BUILD_WEEK_DEMO_SCRIPT.md`
- `docs/ERA_WORK_SAMPLE.md`
- `docs/FINAL_VERIFICATION.md`

### Build Week positioning

`Claros is a voice-first, permissioned worksheet agent that uses GPT-5.6 to understand real document structure, guides students without completing the work for them, and writes only student-approved answers into verified locations.`

### Era positioning

`Claros demonstrates AI operating-system primitives: multimodal perception of a structured surface, object-level state, grounded reasoning, realtime interaction, permissioned actions, safe fallbacks, and deterministic verification.`

### Demo sequence

Target a stable sub-three-minute recording:

1. State the user problem.
2. Upload a nontrivial worksheet.
3. Show GPT-5.6 identify tasks and subparts.
4. Select one task.
5. Talk through it by voice.
6. Interrupt Claros once.
7. State a final answer naturally.
8. Show the proposed answer.
9. Confirm it.
10. Show deterministic write into the worksheet.
11. Show another uncertain task routed automatically to the side panel.
12. Export the original PDF.
13. Briefly show the evaluation scorecard and safety boundary.

Create a separate ~60-second Era version emphasizing AI OS primitives.

### Provenance

Record baseline SHA, final SHA, relevant commits, primary Codex session ID, `/feedback` output, GPT-5.6 usage, Realtime usage if shipped, evaluation commands, known limitations, what existed before Build Week, and what was added during Build Week.

Do not fabricate any session ID.

Acceptance criteria:

- accurate submission draft
- accurate demo script
- Era framing
- final verification report
- all claims linked to evidence
- no hidden limitations
- silver benchmark described without human-gold language

Suggested commit:

`docs(submission): prepare Build Week and Era deliverables`

## Required final verification

At minimum:

```bash
python -m ruff check .
python -m pytest tests/ --cov --cov-config=pyproject.toml --cov-report=term-missing
npm run ci:frontend
docker build -t claros:final .
git diff --check
git status --short
```

Also run:

- silver benchmark validation
- benchmark freeze verification
- compiler evaluation
- browser workflow suite
- PDF visual/export suite
- security suite
- provider mock suite
- live provider checks when credentials exist
- production smoke checks only after deployment

Record exact command output summaries in `docs/FINAL_VERIFICATION.md`.

Do not claim a check passed when it was not run.

## Kill criteria

### GPT-5.6 document compiler

Do not promote it as default when:

- invalid IDs survive validation
- it invents text or coordinates
- unsafe automatic placement occurs on accepted silver
- silver-relative task quality is materially worse than legacy without safety gains
- failures do not degrade safely
- latency or cost is unbounded

Fallback:

- supported selectable-text worksheets
- conservative deterministic regions
- GPT-5.6 tutoring if available
- automatic side-panel fallback
- clear limitations

### OpenAI Realtime

Do not remove Gemini until OpenAI Realtime passes:

- three consecutive live sessions
- interruption
- transcript handling
- provider failure
- typed fallback
- second-workbook state isolation

If Realtime cannot stabilize before submission, keep the migration work on the branch and submit the strongest verified OpenAI document-compiler workflow.

### OCR and broad PDF support

Do not claim general PDF support when scans lack reliable physical evidence, task boundaries remain unresolved, response links are unsafe, or benchmark evidence is weak.

Fallback wording:

`Claros supports structured worksheets and automatically routes uncertain layouts to a safe side panel.`

## Execution behavior

Work through these phases sequentially, with the MVP cut line as the hard priority order.

After every completed phase:

1. run focused tests
2. inspect the diff
3. at red-team checkpoints, use a red-team subagent
4. repair verified issues
5. create a clean commit when the staging set is clear / approved
6. update `docs/BUILD_WEEK_DELTA.md`
7. continue to the next phase

Do not ask for approval between normal implementation phases.

Pause only when an unavoidable external action is required, such as:

- entering an API secret
- granting cloud permissions
- confirming corpus publication rights
- recording or uploading the final video
- submitting the final Devpost form

Also pause on kill-criteria triggers: do not paper over them with documentation claims.

Even when paused for an external action, continue all other work that does not depend on that action.

## Final response checklist

When all possible work is complete, return:

1. final architecture
2. commits created
3. files added, changed, deleted, or intentionally left local
4. test and evaluation results
5. silver benchmark statistics
6. compiler comparison results
7. live OpenAI Realtime verification status
8. deployment status
9. Build Week provenance
10. unresolved external actions
11. strongest remaining risks
12. exact next command for the owner

Be direct.

Do not claim completion for unverified provider or production behavior.

Do not describe the silver benchmark as human gold or human-adjudicated.

Do not reintroduce mandatory teacher review.

Do not weaken student confirmation.

## Start order

1. Read `docs/CLAROS_OPENAI_AUDIT_HANDOFF.md`
2. Read complete Git status and bounded history
3. Inspect the untracked document pipeline
4. Inspect the 17-page pilot materials
5. Inspect the current active upload, session, write, and export paths
6. Execute Phase 0
