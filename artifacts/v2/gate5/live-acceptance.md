# Gate 5 browser and live Realtime acceptance

- Updated: 2026-09-12
- Branch: `codex/claros-v2-nerdy`
- Browser-acceptance implementation checkpoint: `06425f913df328a21abeb73b192760005cee7d34`
- Prior bounded live-provider checkpoint: `22b3d602d5b02711d0997af4fe18ce8945484cf5`
- Realtime model: `gpt-realtime-2.1`
- Semantic model configuration: `gpt-5.6-luna`
- Corpus: checked-in synthetic biology sample and test-owned upload only
- Status: automated browser acceptance and scoped code review pass; physical-microphone and human PDF acceptance remain open
- Conversation-behavior implementation checkpoint: `bcede3835f0512e964c257a48a6a627ece4b1d11`

No API key, ephemeral credential, owner identifier, assignment identifier, raw
provider payload, or private transcript is recorded here. The configured
server-side key was checked only for presence and exact-value absence from
tracked files and the production bundle.

## Baseline defect and classification

At baseline `3d1f7809ef22e28f5203c2425eaf111f98946a80`, the bounded command
`npx playwright test tests/e2e/gate2-workspace.spec.ts --grep "active Question 2" --max-failures=1`
started the legacy Node server on 8787 and Vite on 5173. Vite then proxied the
normal V2 API request to an unstarted process on 8080 and failed with
`ECONNREFUSED 127.0.0.1:8080`; the obsolete fixture-image assertion timed out.
This was a harness/runtime defect plus a retired fixture expectation, not an
application failure.

The repair keeps `npm run test:e2e` in place but builds the actual V2 frontend,
starts the real FastAPI service on dedicated port 18080, uses isolated local
storage, selects the real OpenPDF worker with checksum-verified qpdf, refuses
to reuse another server, and removes only its own test storage on teardown. A
test-build-only import alias replaces the external OpenAI Realtime boundary
with deterministic event replay. FastAPI routes, domain validation,
persistence, review, confirmation, source delivery, export, qpdf, PDFBox, and
OpenPDF remain real. There is no production-accessible fake-mode switch.

Useful retired assertions were mapped as follows:

- Fixture-default `/app` became real sample creation and supported upload
  through `POST /api/v2/assignments`.
- Separate direct/guided route assertions became one adaptive conversation
  with typed and voice-replay intents in the same workspace.
- Fixture-only answer placement became real review, authorization, OpenPDF
  export, PDF parsing/text inspection, and source SHA preservation.
- Existing keyboard, focus, mobile reflow, exact wording, stale review,
  authorization, and axe assertions were retained rather than weakened.

## Coverage

| Check | Evidence type | Source checkpoint | Result | Remaining limitation |
| --- | --- | --- | --- | --- |
| Repaired `npm run test:e2e` launcher and isolation | Automated application-browser diagnostic | `06425f9` | Pass — owns built frontend, FastAPI 18080, storage, qpdf, OpenPDF worker, readiness, and cleanup | External provider is deterministically substituted only at its test import boundary |
| Landing, CTA, sample, supported upload, one conversation, drafts/navigation, review/revision, one authorized approval, acknowledgement, keyboard/mobile, and export | Automated application browser | `06425f9` | Pass — 10/10 Chromium tests in 1.5 minutes | Replay is not physical microphone or audible-playback evidence |
| Captions, independent speaker mute, interruption, active capture controls, terminal disconnect, typed fallback, and retained pause across navigation | Automated Realtime replay through real application UI | `06425f9` | Pass | Does not prove device capture or human hearing |
| Exact command grammar and answer-fidelity regressions | Focused unit/integration plus browser replay | `06425f9` | Pass — questions, negation, extra clauses, and casual agreement rejected; negatives, decimals, fractions, operators, and thousands separators retained | Spoken recognition of the command awaits a human microphone |
| Conversation regressions | Automated frontend integration | `06425f9` | Pass — 48/48 | Provider transport is mocked in deterministic tests |
| Full frontend suite | Automated unit/component/integration | `06425f9` | Pass — 105/105 across 14 files | None |
| Full backend suite | Automated API/security/storage/PDF integration with repository-local qpdf | `06425f9` working tree; final behavioral delta is frontend-only | Pass — 548 passed, 0 skipped, 23 third-party deprecation warnings | No backend file changed after this run |
| OpenPDF publication suite | Automated OpenPDF/qpdf/PDFBox integration | `06425f9` working tree; final behavioral delta is frontend-only | Pass — 22 passed, 0 skipped, 1 third-party warning; qpdf 12.3.2, Java 21.0.10 | Human inspection of the final downloaded PDF remains pending |
| Existing accessibility gate | Storybook Playwright plus in-app axe/keyboard checks | `06425f9` | Pass — all V2 stories, 1/1 sweep; browser workspace axe test also passed | Human assistive-technology evaluation was not requested |
| Format, lint, typecheck, build, bundle, dependency, API, Ruff, strict OpenSpec, and npm audit | Automated contract/build checks | `06425f9` | Pass — 0 npm vulnerabilities; accepted pinned EmbedPDF crypto-externalization and lazy-chunk warnings only | CI will rerun on pull request or main, not on this branch push |
| Server credential and production-bundle secrecy | Automated configuration and exact-value scan | `06425f9` | Pass — server key configured; 0 tracked exact-key matches; 0 production-bundle exact-key matches | No credential value was printed or recorded |
| Bounded live provider: credential issuance, guided typed WebRTC response/captions, mute, interruption, reconnect, direct connect/stop, and cross-question captions | Prior live-provider browser observation | `22b3d60` | Pass for the listed observations | Predates current lifecycle fixes; not a substitute for the remaining human run |
| Scoped independent implementation review | Read-only separate reviewer tracing relevant unchanged callers | `06425f9` | **Approve** — no blocking or material code findings remain | Reviewer correctly left sensory and downloaded-PDF evidence pending |
| Conversation-policy and truthful-action repair | Deterministic effective-session checks plus six bounded typed live-provider sessions | `bcede38` | Action/navigation/status repair passed. Live sessions preserved duplicate-framing, complete-answer, partial-frame, and final declarative-clause failures; policy `.5` closes the last written escape hatch but was not live rerun after the six-session cap. Final `.5`: 110/110 frontend and 76/76 Realtime backend. At unchanged application/PDF shape `6004c8a`: 10/10 browser and 22/22 zero-skip OpenPDF. | Final direct-answer policy needs a future bounded live-provider run; small typed evidence is not universal quality or physical-microphone evidence |
| Direct spoken transcript/candidate and exact spoken confirmation | Human microphone/provider/application evidence | Pending | **Not yet verified** | Requires the user at the prepared local application |
| Audible exact playback and downloaded-PDF inspection | Human sensory and document evidence | Pending | **Not yet verified** | Requires human hearing and inspection of the session export |

The full backend and focused OpenPDF runs initially received an invalid command
environment because `qpdf` is repository-local rather than globally on
`PATH`. They were rerun with
`.local/tools/qpdf/bin/qpdf.exe`; the passing totals above are from those
corrected runs. No dependency skip or renderer fallback remained.

## Scoped independent review

The first review of `82896ea` found three blockers: terminal disconnect could
retain capture intent, late events could cross question boundaries, and browser
coverage omitted caption/mute/interruption integration. The re-review of
`531c1db` found a typed-only `Hear it` completion edge case after assignment
version advancement. The smallest justified fixes pause and mute only after
terminal recovery failure, bind provider events to connection generation plus
assignment/version/question, exercise the missing browser seams, and allow
only local non-mutating `playback_complete` through the stale-version guard.
The final read-only review approved `06425f9`. General PDF selection, cloud
deployment, and unrelated repository domains were out of scope.

## Physical-microphone checklist

Use the sample or another project-owned worksheet. Record observations without
copying a private transcript into this repository.

1. Start speaking and ask about the active question. Verify browser/device
   capture, a provider transcript, and human-audible assistant playback.
2. While Claros speaks, press **Stop listening**. Speak a new short phrase and
   verify it is not transmitted as new input. Separate any already-buffered
   transcription from post-pause speech; a changed label alone is insufficient.
3. Resume capture, type a short message, then speak again. Verify both inputs
   remain in the same conversation.
4. Dictate an answer, navigate to another question conversationally, and
   return. Verify the draft remains attached only to its original question.
5. Enter exact review, press **Hear it**, confirm the wording is audible, and
   say `Use this exact answer` once. Verify exactly one approval and no command
   text in the answer.
6. Request the next question conversationally. Verify capture continues only
   if enabled and remains paused if paused.
7. Complete export and inspect the downloaded PDF. Verify approved wording,
   meaningful punctuation (use a naturally numeric question when available),
   placement, source preservation, and exclusion of an unconfirmed draft.

For the session, keep five evidence categories distinct: browser/device,
provider transcript, application candidate/approval, human audible-playback
confirmation, and downloaded-PDF inspection.

Tasks 5.7 and 5.8 remain open until the required human checks pass and that
evidence is appended. Automated replay is not claimed as human acoustic
acceptance.

## Runtime handoff

The normal `npm start` launcher was run from documentation checkpoint
`6c57b31`, whose application sources are identical to implementation checkpoint
`06425f9`. It produced a fresh production frontend and OpenPDF worker, then
started FastAPI with live OpenAI semantic mapping, live OpenAI Realtime,
OpenPDF, and the checksum-verified repository-local qpdf executable. Both
`GET /health` and `GET /app` returned HTTP 200, and the application was left
running at `http://127.0.0.1:8080/app` for the human session.
