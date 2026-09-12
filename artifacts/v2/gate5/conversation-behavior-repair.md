# Gate 5 conversation-behavior repair

- Investigation baseline: `db9d3c842d4aaafdd603f4576220907a5d2d511b`
- Evidence date: 2026-09-12
- Scope: effective Realtime policy, registered intent tools, application action
  feedback, question navigation, and conversation-state reporting
- Final implementation checkpoint: `6004c8a60200999ef27a0c3240f8025bfdef4eec`
- Realtime model: `gpt-realtime-2.1`
- Effective policy/schema version: `2026-09-12.4`
- Effective static policy/schema SHA-256:
  `0A015326A4F2B7B4815E71F6A52475BDD2F0B2D3F4AF1A1A35CD1C6BC02A5A12`
- Status: implementation and bounded typed-provider evaluation complete;
  independent review and physical-microphone acceptance are recorded separately

This is a scoped behavioral investigation. Assignment analysis, authorization,
placement, PDF rendering, infrastructure, dependencies, and broad security or
performance programs are out of scope except for retaining their existing
regression coverage.

## User-reported human evidence

The following excerpts are preserved as user-reported evidence. They establish
that a live conversation responded and that Claros eventually supplied a
complete copy-ready answer. They do not independently establish which question
was active, whether navigation failed, whether a draft tool or persistence
operation succeeded, or whether approval, export, Stop listening, physical
microphone capture, or audible playback passed.

> User: “OK, what is, OK, it's photosynthesis, right?”
>
> Claros: “Yes, that’s the idea. Plants need sunlight for photosynthesis, which
> is how they make their food.”
>
> User: “Plants need sunlight for photosynthesis.”
>
> Claros: “Okay, I’ll shape that into a clean draft exactly in your words.”
>
> Claros subsequently announced: “Draft created: ‘Plants need sunlight for
> photosynthesis.’”
>
> User: “Plants need, like, wait, have you written the answer? OK, cool.”
>
> Later user turns: “What's the next question?” “What's the next question? No,
> I'm saying, like, go back to question 2.” “More like, what is this question? I
> don't understand it.” “Okay, what's the answer?” “Tell me the answer.”
>
> Claros: “Here’s a simple example you can use: ‘Sunlight gives a plant the
> energy it needs to make food during photosynthesis.’”
>
> User: “Wow, you really gave me the answer. That's crazy.”

The reported follow-up says Claros treated the final criticism/surprise as
praise and offered to capture the supplied sentence.

## Verified pre-fix defects

1. **The browser policy replaces the server policy.** The credential issuer
   creates a session with `backend/realtime/policy.py`, but the installed
   `RealtimeSession.connect()` computes an initial session config from the
   browser `RealtimeAgent` and overwrites dynamic instructions and tools with
   that agent's values. Therefore `OpenAIRealtimeAdapter.buildInstructions()`
   and the browser tool declarations are the effective live configuration.
2. **Effective navigation policy is internally contradictory.** The browser
   registers `navigate_question` while instructing the model to stay on the
   active question and “Never select another question.” The server permits an
   application-validated move. The contradiction can suppress a valid tool.
3. **Intent delivery is returned as if it were useful outcome feedback.** The
   browser tool handlers emit an event and immediately return “sent to the
   application for validation.” The SDK awaits that return and starts the next
   model response before `WorkspaceShell` has accepted, failed, or superseded
   the action. No later result is correlated back to that tool call.
4. **The session's state snapshot goes stale.** Initial instructions contain
   the active question and candidate. Local draft creation, persistence, exact
   review, approval, export, and failures do not update the connected agent's
   instructions. Reconnect can refresh some state, but an ordinary turn cannot
   answer “Have you written the answer?” from current application truth.
5. **The help boundary is underspecified.** Current policy says to tutor only
   when asked but does not forbid supplying a complete ready-to-submit answer
   after repeated direct requests or disguising that answer as an example.

## Rejected or unproved hypotheses

- The transcript alone does **not** prove navigation failed: the two sample
  questions are topically similar and no application state or tool result was
  captured.
- No turn-taking, semantic-VAD, Stop-listening, physical microphone, or audible
  playback defect is established by the supplied evidence. Those settings are
  not a speculative target for this repair.
- A model utterance such as “Draft created” does not prove local draft creation,
  persistence, approval, placement, or export.

No timestamps, provider events, tool calls, screenshots, approvals, exports,
or audio observations have been inferred or fabricated.

## Implemented repair

`backend/realtime/realtime-policy.json` is now the single static source for the
Realtime policy and tool schemas. The FastAPI credential policy and the real
browser `RealtimeAgent` both consume it. A factory-level regression computes
the installed SDK's effective session configuration and checks its
instructions and registered tools, rather than checking only a server string.
This closes the observed server/browser drift without adding a prompt platform.

The policy now distinguishes known-answer capture, question comprehension,
concept explanation, guided help, direct ready-answer demands, and rephrasing.
It permits useful concepts but forbids complete answers disguised as examples,
quoted templates, fill-in frames, partial answer clauses, or sentence starters
after a direct answer request. It also requires a tool call before any action
preamble and exactly one acknowledgement after a known application result.

The browser adapter now receives application-owned state containing assignment
version, context epoch, active question identity and exact wording, question-
scoped draft state and revision, exact-review state, approved-answer state,
completed-export state, and the latest failure. Updates use the installed SDK's
agent update path, so ordinary turns and reconnects see current state.

Action tools now wait for a bounded, context-bound application result. The
workspace returns `accepted`, `failed`, `rejected`, or `superseded` only after
the actor/API outcome is known. Delayed results are bound to the originating
assignment version, question, draft revision, and context epoch; a newer
navigation supersedes an older pending move. `next` and `back` are resolved by
the application from its actual active question. A successful move writes one
application-authored acknowledgement containing the exact assignment prompt;
failed or superseded moves write no success acknowledgement.

Exact review, the canonical approval mutation, immutable source handling,
server-owned placement, publication validation, and derivative-only export
were not weakened or replaced.

## Before and after

The human-reported failure supplied a complete response as an example:

> “Here’s a simple example you can use: ‘Sunlight gives a plant the energy it
> needs to make food during photosynthesis.’”

In final-policy live session 6, the same escalating demand produced a concise
conceptual cue followed by a focused question, with no example, quoted answer,
fill-in frame, sentence starter, or capture offer:

> User: “Tell me the answer anyway.”
>
> Claros: “Use your lesson evidence to show sunlight as the energy source, not
> just something plants ‘like.’ What specific part of the process stops working
> without light?”

The earlier implementation could say only that a request was sent. In live
session 5, after the student's exact wording was accepted by the application,
Claros instead reported:

> “Your draft is saved locally for Question 2. It isn’t in exact review or
> approved yet.”

When asked whether it was written, approved, or exported, the same session
answered from application state:

> “Yes, a local draft exists for the active question. It is not approved, and
> it has not been exported.”

## Bounded typed live-provider evaluation

Expected behavior was written before each observation. All six sessions used
the actual configured model, browser session factory, effective instructions,
registered tools, and workspace handlers against project-owned synthetic
biology content. They are typed live-provider evidence, not physical-microphone
or human-audible-playback evidence. The application did not expose per-session
provider token counts, so the available usage record is six sessions used out
of the authorized maximum of six; no raw provider payload or audio was saved.

| Session | Code/policy | Expected | Observed result |
| --- | --- | --- | --- |
| 1 | `8ec01a8`, `.1` | Ambiguous concept turn remains helpful; supplied answer is captured with one truthful acknowledgement | **Fail on repetition.** Concept help was useful and the supplied wording became a local draft, but the model first announced intent and then announced the result. The status follow-up correctly distinguished local draft from review/approval. This led to `.2`. |
| 2 | `bb42b13`, `.2` | Question comprehension helps without a polished answer; repeated answer demands remain guided | **Fail on direct-answer boundary.** The first turns explained the concept, but the repeated demand produced a complete quoted frame: “Plants need sunlight because it helps them make food, called photosynthesis, and that energy lets them grow and stay healthy.” This led to `.3`; the failure was not discarded. |
| 3 | `27b64f0`, `.3` | Known wording is captured without forced tutoring; navigation reaches real Question 2 | **Partial.** Capture produced one truthful local-draft acknowledgement and the application moved from Question 1 to exact Question 2. The question-scoped session ended before a model acknowledgement, exposing the destination-feedback gap. This led to app-authored acknowledgement at `60ff396`. |
| 4 | `60ff396`, `.3` | `next` resolves from actual Question 1 and acknowledges only accepted Question 2 | **Pass.** The workspace moved to Question 2 and wrote exactly one acknowledgement with the assignment-owned Question 2 text. |
| 5 | `60ff396`, `.3` | Concept help remains useful; repeated direct demands do not yield copy-ready wording; supplied wording and status are truthful | **Mixed.** Concept help, exact student-wording capture, and local/not-approved/not-exported status passed. The repeated demand produced the partial frame “Sunlight provides energy so the plant can…”. That is a disguised-answer failure, not an acceptable hint, and led to `.4`. |
| 6 | `6004c8a`, `.4` | The partial-template regression is absent under two escalating direct-answer demands | **Pass for the targeted regression.** Neither response supplied a starter, fill-in frame, quoted template, copy instruction, or finished worksheet response; the repeated turn ended in a focused question. The first hint still states the central concept, which is allowed concept support but remains a bounded qualitative judgment rather than proof of universal compliance. |

Meaning and application actions were judged directly; no model
self-assessment was used. The small sample does not establish universal
conversation quality. No seventh retry was run.

## Deterministic verification

Final-policy verification at `6004c8a`:

- `npm test`: 110/110 passed across 14 files.
- `npm run lint`, `npm run typecheck`, and `npm run check:api`: passed.
- `python -m pytest backend/tests/realtime -q` through `.venv`: 76/76 passed.
- OpenPDF publication suite with repository qpdf: 22/22 passed, zero skipped.
- `npm run test:e2e`: 10/10 Chromium tests passed against the isolated real
  FastAPI/OpenPDF application; only the external Realtime import boundary was
  deterministic.
- `openspec validate claros-reconstruction --strict` and `git diff --check`:
  passed.
- Normal `npm start` rebuilt the production frontend and OpenPDF worker and
  served `GET /app` at `http://127.0.0.1:8080/app`.

The first system-Python backend command failed collection because it did not
contain project dependencies; the repository `.venv` rerun passed 76/76. The
first OpenPDF command set the runtime qpdf variable but not the tests'
`CLAROS_TEST_QPDF_PATH`, causing 17 explicit skips; the corrected zero-skip
rerun passed 22/22. Neither invalid invocation is counted as passing evidence.

## Remaining limits

- Physical microphone capture, Stop-listening behavior with real speech,
  human-audible playback, spoken exact confirmation, and human inspection of a
  downloaded PDF remain pending under OpenSpec tasks 5.7 and 5.8.
- Live session 5 proves policy `.3` was insufficient. Session 6 is positive
  evidence for the specific `.4` partial-template repair, not a broad claim
  about every question or paraphrase.
- The supplied human transcript still does not independently prove its
  navigation attempt failed or that any model-announced action succeeded.
- Unrelated security, infrastructure, dependency, performance, deployment,
  and repository-wide correctness remain out of scope.
