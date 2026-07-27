# Claros Revamp Roadmap

## Status

Claros is entering a focused product revamp.

The objective is not to rewrite the application or expand scope. The objective is to converge the current prototype into a coherent, reliable, accessible product with one document model, one runtime AI strategy, a real sample flow, strong browser behavior, and verified safety.

Historical audits, Build Week plans, parser experiments, benchmark reports, and handoff documents remain useful context, but this document is the canonical implementation roadmap for the revamp.

---

# 1. Product Definition

Claros is a voice-guided worksheet assistant primarily for students who have difficulty typing.

The intended product flow is:

1. A student uploads a worksheet or selects a built-in sample worksheet.
2. Claros identifies the student-facing tasks and physical response areas.
3. The student selects or discusses a task.
4. Claros guides the student through reasoning using voice or typed interaction.
5. The student states or explicitly approves their final answer.
6. Claros may write only that approved answer for that task.
7. The answer is placed into the correct worksheet response area.
8. The student exports the completed original worksheet as a PDF.

## Non-negotiable integrity rule

Claros must never write an answer for a task until the student has stated or explicitly approved that answer for that specific task.

No model may:

- invent approval,
- authorize writing,
- change an approved answer after confirmation,
- invent PDF geometry,
- silently write to an uncertain destination.

---

# 2. Current Revamp Scope

The revamp is intentionally narrow.

The initial supported worksheet target is:

- selectable-text PDFs,
- student-facing worksheets,
- clear task boundaries,
- clear reading order,
- multiple questions per document,
- explicit answer lines, boxes, checkboxes, or bounded writable areas,
- simple multi-page documents where page boundaries are unambiguous.

The following are not current acceptance targets:

- OCR-heavy scans,
- mixed teacher/student packets,
- complex tables,
- map or image-dependent worksheets,
- unusual multi-column packets,
- external-resource-dependent activities,
- arbitrary real-world educational PDFs.

The historical acceptance corpus remains a later stress suite. It must not pull the product back into premature complexity.

---

# 3. Canonical Product Samples

Claros should ship three first-party sample worksheet types. These are both product assets and deterministic evaluation fixtures.

Every sample document must contain multiple questions/tasks.

## 3.1 Short Answer

A self-contained worksheet with multiple short-answer questions.

It should exercise:

- multiple numbered tasks,
- one-line responses,
- larger response boxes,
- clear prompt ordering,
- straightforward task-to-response relationships.

## 3.2 Multiple Choice + Explanation

A self-contained worksheet with multiple choice questions.

It should exercise:

- multiple questions,
- structured A/B/C/D choices,
- checkbox/control regions,
- some tasks with an additional explanation response,
- multiple response regions attached to one logical task.

## 3.3 Math / Numeric Practice

A self-contained worksheet with multiple numeric or word problems.

It should exercise:

- multiple numbered problems,
- explicit numeric answer fields,
- optional “show your work” areas,
- multiple response regions under one task where appropriate.

## Product rule for samples

Samples must use the real assignment flow.

Do not create a fake demo-only runtime.

A sample should behave like a normal uploaded assignment for:

- task selection,
- typed interaction,
- voice interaction,
- confirmation,
- writing,
- persistence,
- refresh/restore,
- export,
- deletion.

---

# 4. Runtime AI Strategy

Claros will standardize its production AI runtime on Gemini for simplicity.

This is an operational decision, not a claim that all product behavior should be model-driven.

Use Gemini for:

- realtime tutoring and voice,
- semantic reasoning where deterministic evidence is insufficient,
- structured interpretation of ambiguous worksheet semantics.

Use deterministic code for:

- PDF geometry,
- text block extraction,
- lines,
- rectangles,
- checkboxes,
- widgets,
- stable IDs,
- page coordinates,
- obvious writable-region extraction,
- obvious task-to-response associations,
- closed-world validation,
- confirmation,
- write authorization,
- answer placement,
- exact approved-answer handling,
- PDF export.

## Remove GPT/OpenAI runtime complexity

Audit the complete runtime for:

- OpenAI/GPT provider code,
- semantic compiler adapters,
- environment variables,
- dependencies,
- feature flags,
- tests,
- documentation,
- deployment assumptions,
- provider-switching abstractions that no longer serve a real need.

Once equivalent required behavior is confirmed through Gemini or deterministic code:

- remove OpenAI production runtime paths,
- remove GPT semantic compiler paths,
- remove OpenAI-specific runtime dependencies,
- remove unused provider configuration,
- remove tests that exist only to preserve removed provider implementations,
- remove stale OpenAI-specific active documentation.

Codex remains a development tool only. It is not part of the Claros production runtime.

---

# 5. Confirmed Answer Contract

After a student approves an answer, Claros should not pass that answer through another LLM simply to rewrite it.

The approved text is the source of truth.

Allowed post-confirmation operations are deterministic and presentation-only, such as:

- trimming accidental leading/trailing whitespace,
- normalizing line endings,
- line wrapping,
- choosing font size,
- fitting text into a validated response area.

Any transformation that could alter visible characters or meaning must happen before approval or be shown to the student for approval.

---

# 6. Mandatory Stage Workflow

Every stage below must follow the same lifecycle.

No stage begins directly on `main`.

## Phase A: branch

Before each stage:

1. switch to current `main`,
2. update from the remote,
3. inspect the working tree and preserve unrelated work,
4. create a new branch dedicated to that stage.

Every later stage begins from the newly merged and updated `main`.

## Phase B: audit

Before modifying code:

- inspect the relevant runtime path,
- inspect existing implementation,
- inspect current tests,
- inspect browser behavior where applicable,
- identify dead code,
- identify redundant tests,
- identify duplicated state or schemas,
- identify stale assumptions,
- identify security and reliability risks.

Do not start by coding from the roadmap blindly. First verify the current tree.

## Phase C: baseline

Run the relevant existing checks and record:

- current behavior,
- test results,
- benchmark results,
- browser/UI behavior,
- known failures.

## Phase D: fix

Implement the smallest coherent change set that satisfies the stage.

Avoid pulling work from later stages into the current branch.

## Phase E: verify

Run all relevant:

- unit tests,
- integration tests,
- frontend tests,
- parser/canonical tests,
- lint/static checks,
- browser flows,
- accessibility checks,
- deployment/config checks.

## Phase F: red team

After the implementation appears correct, actively try to break it.

Question:

- stale state,
- malformed input,
- invalid IDs,
- concurrency,
- refresh,
- mobile,
- keyboard/screen-reader behavior,
- provider failure,
- storage failure,
- model hallucination,
- duplicated state,
- obsolete tests,
- false-positive test coverage.

Where the stage affects UI, inspect the live UI. Do not rely only on source inspection.

## Phase G: fix red-team findings

Resolve all P0/P1 findings caused or exposed by the stage.

Add regression coverage where it protects real product behavior.

Do not continue to the next stage with an unresolved blocker.

## Phase H: final review

Review the complete diff for:

- accidental generated output,
- obsolete compatibility code,
- duplicate logic,
- stale comments,
- dead imports,
- dead tests,
- debug code,
- misleading documentation.

## Phase I: push and merge

Push the branch and ensure CI passes.

Merge into `main` only when:

- stage acceptance criteria pass,
- red-team findings are resolved,
- relevant tests pass,
- CI passes,
- no known P0/P1 regression remains.

Then update local `main`, verify the merged result, and create a new branch for the next stage.

---

# 7. Stage 1 — Immediate Runtime Safety and Provider Consolidation

## Audit

Audit the active runtime for:

- provider selection,
- parser mode,
- Gemini configuration,
- OpenAI/GPT configuration,
- deployment environment,
- startup validation,
- missing-key behavior,
- rate limiting,
- dependency vulnerabilities,
- public debug/test surfaces,
- legacy answer-generation paths,
- browser injection sinks.

### Mandatory XSS regression audit

A previous audit identified a stored DOM XSS risk in worksheet rendering where uploaded/parser-controlled worksheet labels could flow into `innerHTML`.

Do not assume this is still present or already fixed.

Audit the current tree for:

- `innerHTML`,
- `outerHTML`,
- `insertAdjacentHTML`,
- dynamic HTML templates,
- any equivalent DOM sink.

Trace whether values can originate from:

- uploaded PDFs,
- parser output,
- semantic model output,
- assignment manifests,
- user answers.

If the old vulnerable path is already gone, prove the current path is safe and retain regression coverage.

## Fix

- make runtime provider configuration explicit,
- consolidate production AI runtime on Gemini,
- remove GPT/OpenAI runtime paths once no longer required,
- remove post-confirmation LLM rewriting,
- fix rate-limit paths that can return internal errors,
- remove or gate production debug/test routes,
- fix unsafe DOM interpolation,
- establish baseline CSP/security headers where compatible,
- make invalid production configuration fail clearly.

## Red team

Test:

- malicious worksheet labels,
- HTML-like parser values,
- missing Gemini credentials,
- invalid model configuration,
- rate-limit exhaustion,
- provider failure,
- disabled semantics,
- malformed provider output,
- production route inventory,
- startup configuration mismatch.

## Acceptance

- no untrusted document content can execute in the app origin,
- no OpenAI/GPT production path remains without a current justified dependency,
- confirmed answers are not rewritten by an LLM,
- production configuration cannot silently select an unavailable provider,
- runtime failure paths return intentional errors.

---

# 8. Stage 2 — One Canonical Production Document Model

## Audit

Trace every document/task representation through:

- physical extraction,
- semantic interpretation,
- persistence,
- API payloads,
- frontend state,
- worksheet rendering,
- confirmation,
- writing,
- export,
- canonical evaluation.

Find every assumption that:

- one task has one answer region,
- answer regions are untyped,
- choices are embedded in prompt text,
- array position is identity,
- answer state belongs inside immutable parser output.

Identify all duplicate or parallel schemas.

## Fix

Converge on one production representation capable of expressing:

- document identity and schema version,
- pages and page roles,
- source blocks/evidence,
- tasks,
- task ordering,
- prompt text,
- prompt region references,
- parent/subpart relationships,
- structured choices,
- zero/one/many response regions,
- stable response-region IDs,
- response type,
- response safety,
- task-to-response relationships,
- side-panel fallback,
- separate draft/confirmation/write state.

Avoid maintaining an evaluation-only model that production cannot represent.

## Red team

Test:

- zero regions,
- one region,
- multiple regions,
- many checkboxes,
- multiple pages,
- choices plus explanation,
- task subparts,
- unsafe/unknown regions,
- duplicate IDs,
- invalid relations,
- cross-page relations,
- serialization round trips,
- old persisted assignments if compatibility is required.

## Acceptance

One authoritative document contract can represent every canonical sample without lossy adaptation.

---

# 9. Stage 3 — Deterministic Canonical Extraction

## Audit

Run all canonical samples through the actual production path.

For every missed task, region, type, or relation, determine the concrete cause.

Inspect:

- selectable text,
- vector lines,
- rectangles,
- widgets,
- checkbox sizes,
- reading order,
- prompt boundaries,
- choice labels,
- response candidates,
- candidate merging,
- geometry normalization,
- task-to-region association.

## Fix

Make deterministic extraction reliable for canonical documents.

Support:

- answer lines,
- bounded boxes,
- checkbox controls,
- explicit writable regions,
- stable physical IDs,
- structured choices,
- multiple response regions per task,
- separate “answer” and “show your work” regions,
- deterministic task-to-region relationships where layout makes them obvious.

Do not union distinct response areas into one task-level bbox.

Use Gemini only where semantic ambiguity remains after deterministic extraction.

## Red team

Perturb:

- spacing,
- line length,
- box size,
- checkbox size,
- question count,
- prompt length,
- choice length,
- page breaks,
- response spacing.

Verify the implementation follows document structure rather than fixture-specific wording or hardcoded coordinates.

## Acceptance

Canonical release target:

- all expected tasks detected,
- all intended response regions detected,
- correct region types,
- correct associations,
- zero false-positive writable regions,
- stable results across repeated generation and parsing.

Do not alter ground truth to improve results.

---

# 10. Stage 4 — Canonical Sample Product Flow

## Audit

Audit all current sample/demo behavior.

Identify:

- old algebra/test assets,
- fake demo paths,
- sample-specific state behavior,
- dead-end sample flows,
- special-case storage/session behavior.

## Fix

Make the three canonical worksheets the official sample system:

- Short Answer,
- Multiple Choice,
- Math Practice.

Each contains multiple questions.

Samples must use the normal Claros assignment path.

## Red team

For every sample test:

- task switching,
- multiple answers,
- partial completion,
- edit before approval,
- edit after approval,
- refresh,
- write failure,
- export with zero answers,
- export with partial answers,
- full completion,
- deletion.

## Acceptance

All three samples demonstrate the real Claros loop without special demo behavior or dead ends.

---

# 11. Stage 5 — State, Confirmation, Writing, and Export Integrity

## Audit

Trace ownership of:

- assignment state,
- selected task,
- drafts,
- proposed answers,
- confirmed answers,
- write authorization,
- written state,
- export state.

Inspect refresh, failure, retry, and concurrency behavior.

## Fix

Ensure:

- exact task-scoped approval,
- complete refresh restoration,
- safe retries,
- atomic/idempotent write authorization,
- replay rejection after success,
- placement revalidation before modifying PDFs,
- coherent zero-answer export,
- coherent partial export,
- persisted answer state separate from immutable parser evidence.

## Red team

Test:

- refresh at every flow stage,
- double-clicking,
- stale sessions,
- simultaneous writes,
- storage failure,
- write retry,
- replay,
- changed confirmed text,
- invalid region IDs,
- deletion during an active session.

## Acceptance

The confirmation invariant survives refresh, retries, concurrency, and storage/provider failures.

---

# 12. Stage 6 — Frontend Architecture Audit and Product UI

## Audit

Audit both source architecture and the live browser experience.

Inspect:

- landing,
- empty state,
- sample selection,
- upload,
- processing,
- workspace,
- task navigation,
- choices,
- multiple response regions,
- voice states,
- confirmation,
- writing,
- side-panel fallback,
- errors,
- export,
- restore.

Identify:

- monolithic modules,
- duplicate state,
- dead renderers,
- duplicated API logic,
- unused helpers,
- frontend/backend disagreement.

Do not migrate frameworks merely for style.

## Fix

Keep the current frontend technology unless real complexity proves otherwise.

Modularize responsibilities where needed.

The UI must clearly support:

- multiple tasks,
- choices,
- multiple response regions,
- sample selection,
- exact answer approval,
- clear destination,
- safe fallback,
- restored state.

## Red team

Test:

- desktop,
- laptop,
- tablet,
- ~390px mobile,
- long prompts,
- many tasks,
- many choices,
- multi-page samples,
- long approved answers,
- error states,
- partial completion.

A student should always be able to answer:

- What task am I on?
- Is Claros listening?
- What exact answer am I approving?
- Where will it go?
- Has it been written?
- What do I do next?

## Acceptance

Frontend state matches backend state and the canonical document model is represented without hidden hacks.

---

# 13. Stage 7 — Dedicated Visual Design Audit and Polish

This is a product-design stage, not merely a CSS cleanup.

## Audit

Visually inspect every major product state.

Evaluate:

- information hierarchy,
- typography,
- spacing,
- visual rhythm,
- neutral surfaces,
- orange accent use,
- contrast,
- worksheet prominence,
- task navigation,
- answer overlays,
- toolbar density,
- voice panel,
- confirmation UI,
- mobile layout,
- empty states,
- loading,
- errors,
- sample cards,
- landing page.

Target character:

- calm,
- precise,
- academic,
- trustworthy,
- accessible,
- worksheet-centered,
- voice-first,
- restrained,
- not generic AI SaaS,
- not hackathon-demo UI.

## Fix

Refine actual weak points discovered in the running product.

Do not redesign for novelty.

## Red team

Look for:

- overflow,
- clipped content,
- layout shifts,
- tiny hit targets,
- mobile obstruction,
- low contrast,
- excessive cards,
- excessive decoration,
- inconsistent spacing,
- unclear states,
- confusing status colors.

## Acceptance

Landing, setup, worksheet, voice, confirmation, and export feel like one deliberate product.

---

# 14. Stage 8 — Mobile and Accessibility

## Audit

Test:

- keyboard-only operation,
- focus order,
- screen-reader semantics,
- task navigation,
- choices,
- answer controls,
- live regions,
- error announcements,
- focus restoration,
- 200% zoom,
- reduced motion,
- touch targets,
- mobile fit width,
- mobile voice panel,
- microphone denial,
- typed fallback.

## Fix

- expose semantic task content alongside the visual worksheet,
- keep all core flows usable without voice,
- keep all core flows usable without precise pointer input,
- implement true scale-to-container behavior,
- prevent the voice interface from obscuring the worksheet during ordinary use.

## Red team

Test narrow screens, high zoom, keyboard flows, long content, and screen-reader-oriented structure.

## Acceptance

Accessibility is part of core behavior, not an afterthought.

---

# 15. Stage 9 — Gemini Voice Architecture

## Audit

Audit the current Gemini Live path end-to-end:

- ephemeral credentials,
- connection lifecycle,
- microphone pipeline,
- audio capture,
- resampling,
- turn detection,
- transcription,
- interruption,
- task selection,
- answer proposal,
- connection limits,
- reconnect,
- session resumption,
- typed fallback.

Identify deprecated browser APIs and fragile transcript heuristics.

## Fix

Keep Gemini as the production voice provider, but isolate provider transport from product state.

Prefer structured product events such as:

- task selected,
- student message,
- hint requested,
- answer proposed,
- answer rejected,
- answer approved.

The model may propose an answer.

Only product/server state may approve it.

Improve interruption, audio processing, reconnect, and fallback behavior.

## Red team

Test:

- mic denial,
- noise,
- rapid turn-taking,
- interruption,
- long sessions,
- connection loss,
- reconnection,
- task switching,
- proposal for wrong task,
- repeated/partial transcript,
- provider outage,
- typed continuation after voice failure.

## Acceptance

Voice failure cannot destroy assignment state or confirmed work.

---

# 16. Stage 10 — Test Suite Audit and Rationalization

Do not treat test count as quality.

## Audit

Inventory the full test suite.

For every test family ask:

- what product risk does this protect?
- is the behavior still active?
- is another test already stronger?
- is this testing implementation rather than behavior?
- does it test dead code?
- is it tied to removed OpenAI/GPT runtime code?
- is it tied to historical parser architecture?
- is it redundant with canonical tests?
- can it pass while the real product is broken?

Identify:

- obsolete provider tests,
- duplicate parser tests,
- dead renderer tests,
- dead feature-flag tests,
- redundant fixtures,
- weak implementation-coupled tests.

## Fix

Remove or consolidate redundant tests.

Organize coverage around actual product risks:

- document schema,
- geometry,
- canonical parser behavior,
- task-region relationships,
- state restoration,
- confirmation,
- writing,
- concurrency,
- lifecycle,
- Gemini integration boundaries,
- frontend state,
- browser flows,
- accessibility,
- export.

## Red team

Where practical, introduce representative local mutations and verify the suite catches:

- missing checkbox extraction,
- wrong region association,
- changed confirmed text,
- refresh loss,
- token replay,
- provider outage,
- broken mobile fit width,
- inaccessible task navigation,
- broken sample flow.

## Acceptance

Every major test family has a clear product-risk purpose.

The suite is allowed to become smaller if it becomes more meaningful.

---

# 17. Stage 11 — Security, Privacy, and Lifecycle

## Audit

Trace sensitive data:

- PDFs,
- previews,
- manifests,
- task text,
- drafts,
- answers,
- confirmed text,
- sessions,
- transcripts,
- audio,
- provider payloads,
- logs,
- metrics,
- exports.

Determine:

- storage location,
- authorization,
- expiry,
- actual deletion,
- provider exposure,
- browser-held secrets,
- production exposure.

## Fix

Implement a coherent verified lifecycle.

Assignment deletion must remove all associated persisted state.

Retention claims must match actual storage lifecycle behavior.

Harden browser/API boundaries.

Resolve vulnerable runtime dependencies.

Do not log educational content unless explicitly necessary.

## Red team

Test:

- expired assignment,
- deleted assignment,
- stale session,
- replayed capability,
- missing authorization,
- malformed IDs,
- oversized uploads,
- rate-limit bypass,
- provider error leakage,
- log exposure,
- multiple Cloud Run instances.

## Acceptance

Privacy and security statements describe verified technical behavior.

---

# 18. Stage 12 — Observability, Performance, and Deployment

## Audit

Audit:

- Cloud Run configuration,
- CI/deploy workflow,
- environment variables,
- secrets,
- GCS,
- CPU/memory assumptions,
- concurrency,
- timeout,
- scaling,
- health checks,
- provider costs,
- static assets,
- upload request execution.

Specifically verify whether PDF parsing/semantic work blocks the async request/event loop.

## Fix

- make Cloud Run behavior explicit and reproducible,
- move CPU-heavy/blocking document work off the request event loop,
- add bounded execution and timeouts,
- make Gemini the only required runtime AI provider,
- establish distributed/shared abuse and spend controls appropriate for Cloud Run,
- lazy-load heavy Gemini browser assets when voice starts where practical,
- optimize oversized static assets where useful.

Add content-free metrics for:

- uploads,
- parse latency,
- candidate counts by type,
- semantic compilation,
- validation rejection,
- side-panel fallback,
- voice connect/disconnect/reconnect,
- time to first audio,
- answer proposals,
- confirmations,
- writes,
- placement rejection,
- exports,
- deletion,
- provider errors,
- measurable provider cost.

## Red team

Test:

- Gemini unavailable,
- GCS errors,
- two heavy uploads,
- health/API responsiveness during parsing,
- Cloud Run scaling,
- missing secrets,
- bad environment,
- memory pressure,
- request timeout,
- multi-instance limiting.

## Acceptance

The deployed system fails predictably, remains diagnosable, and does not expose student content through observability.

---

# 19. Stage 13 — Documentation and Repository Convergence

## Audit

Find:

- stale README claims,
- outdated architecture diagrams,
- OpenAI/GPT references,
- historical parser plans presented as current,
- obsolete Build Week plans,
- duplicate current roadmaps,
- old provider handoffs,
- stale feature flags,
- misleading sample/OCR claims.

## Fix

Converge active documentation on the actual current product.

Historical evidence may remain but must be clearly historical.

The active repository should clearly explain:

- what Claros is,
- what document types are currently supported,
- how Gemini is used,
- what remains deterministic,
- the confirmation invariant,
- the sample system,
- deployment,
- privacy/lifecycle,
- canonical evaluation scope.

## Red team

Approach the repository as a new engineer.

Can someone correctly understand the current product without reconstructing years of historical experiments?

## Acceptance

The repository has one coherent present tense.

---

# 20. Stage 14 — Final Whole-Product Audit

Do not add major new features here.

## Audit

Exercise:

- all canonical samples,
- real upload,
- multiple tasks,
- choices,
- explanations,
- numeric tasks,
- multiple response regions,
- voice,
- typed fallback,
- confirmation,
- writing,
- partial completion,
- full completion,
- refresh,
- mobile,
- accessibility,
- export,
- deletion,
- provider failure,
- storage failure.

Repeat:

- architecture audit,
- parser audit,
- frontend audit,
- visual design audit,
- API audit,
- test-suite audit,
- security audit,
- accessibility audit,
- deployment audit.

## Red team

Evaluate Claros as if preparing it for a real student pilot.

Find anything that makes it feel:

- confusing,
- fragile,
- inaccessible,
- unsafe,
- misleading,
- internally inconsistent,
- unfinished.

Fix P0/P1 findings before declaring the revamp complete.

## Final acceptance bar

Claros can exit the canonical revamp when:

- all three canonical documents contain multiple tasks,
- all three complete successfully through the real product path,
- canonical task extraction is reliable,
- canonical response-region extraction is reliable,
- task-region associations are reliable,
- false writable regions are eliminated,
- sample and upload flows share the same core path,
- refresh preserves usable state,
- exact confirmation is preserved,
- writing is deterministic and safe,
- export is reliable,
- mobile is usable,
- typed fallback is complete,
- Gemini failure does not break product state,
- lifecycle behavior is verified,
- security regression paths are covered,
- test coverage protects meaningful product risks,
- obsolete/redundant runtime and test paths are removed,
- active documentation matches reality.

Only after this should Claros expand toward:

- OCR,
- scanned worksheets,
- complex tables,
- mixed packets,
- visual-heavy tasks,
- unusual layouts,
- broad real-world worksheet claims.

---

# 21. Revamp Rules

Throughout the revamp:

- Do not expand scope because an edge case is interesting.
- Do not preserve dead architecture merely because tests exist for it.
- Do not add a model call where deterministic logic is sufficient.
- Do not let Gemini invent PDF geometry.
- Do not let Gemini authorize writing.
- Do not alter confirmed answer meaning.
- Do not use raw test count as a quality metric.
- Do not treat unit-test success as proof the UI works.
- Audit relevant UI states visually.
- Red-team every stage before merge.
- Resolve P0/P1 stage regressions before continuing.
- Merge a completed stage into `main` before starting the next stage.
- Start every stage from fresh, updated `main`.
- If acceptance criteria cannot be met, stop and report the blocker rather than hiding it behind documentation or moving on.
