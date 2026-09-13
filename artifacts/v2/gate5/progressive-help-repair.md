# Gate 5 progressive-help repair

- Investigation baseline: `2ae2cf3e4651d56fe64db556856ef6942233a6ea`
- Evidence date: 2026-09-13
- Scope: repetitive tutoring under the effective Realtime conversation policy
- Final implementation checkpoint:
  `85cbf95921a2c63b876b3aa43f0fce2390fd235c`
- Realtime model: `gpt-realtime-2.1`
- Final policy version: `2026-09-13.2`
- Final policy SHA-256:
  `58FB11E7A0C0CA40D0D94B6FC1B77BC05B4B4298DCF8070ED474CE1ACC4916D1`
- Status: final policy passed the bounded typed live evaluation; physical
  microphone and human PDF acceptance remain pending

## User-reported human evidence

The supplied microphone transcript establishes one narrow failure. The first
guiding question was reasonable, direct-answer leakage was absent, and the
next three Claros turns kept asking for substantially the same missing idea in
different words. It does not establish a microphone, navigation, approval, or
export defect.

Question: “Why do plants need sunlight? Use evidence from the lesson in one or
two sentences.”

1. Student: “What's the answer for number one?”
   Claros: “What’s one thing from your lesson that shows what happens to a
   plant when it gets sunlight? For example, think about whether it helps the
   plant make something or do something important.”
2. Student: “Tell me the answer.”
   Claros: “What evidence did your lesson give about what sunlight allows a
   plant to do, like making something it needs?”
3. Student: “Are you going to tell me the answer or not?”
   Claros: “What did the lesson say happens if a plant does not get enough
   sunlight, and how does that connect to why it needs it?”
4. Student: “응.”
   Claros: “What example from your lesson shows how sunlight helps a plant make
   its food?”

## Established pre-change root cause

Policy version `.5` leaves repeated questioning as the model's safest response
to repeated direct-answer requests:

1. `backend/realtime/realtime-policy.json` requires one focused question after
   a ready-answer request and says repeated demands do not remove that rule.
2. The same policy prohibits a complete answer, examples, sentence starters,
   partial clauses, fill-in frames, and stating the requested relationship.
3. It permits concept explanation when a student separately asks about a
   concept, but does not say that Claros may change to a concise concept
   explanation when a focused question has failed.
4. The result is locally safe but globally repetitive: paraphrasing the focused
   question satisfies every explicit `.5` instruction.

This is not caused by missing transcript data. The browser
`OpenAIRealtimeAdapter` receives `WorkspaceShell`'s conversation turns, retains
the last 12 turns, appends both typed/spoken student turns and Claros turns, and
places them in the effective `UNTRUSTED_WORKSHEET_DATA.recent_conversation`
payload. Turns carry application-owned question identifiers. The connected
provider session also retains its native conversation. A new tutoring-state
framework is therefore not justified for this repair.

The live model receives the browser adapter's policy and tools from the same
authoritative JSON as the server credential request. The installed SDK session
configuration test verifies that browser authority. No provider, microphone,
navigation, approval, placement, or PDF architecture change is needed.

## Implementation and final evidence

The single authoritative policy now tells Claros to use the least demanding
intervention that moves the student forward, consult recent question-tagged
conversation turns, and change strategy when an intervention fails. The
progression permits one focused question, a one-component concept explanation,
a terse list of needed concepts, and an invitation for student wording. It does
not require every level and stops tutoring immediately when the student supplies
a usable answer.

The first `.1` live run exposed an ambiguity in “one component”: the model
combined a concept explanation, consequences, and an invitation into a full
answer. Final `.2` therefore limits direct-answer escalation to one assistance
level per turn. A Level 2 turn explains exactly one concept and leaves out at
least one substantive idea, evidence item, or reasoning link required by the
prompt. A Level 3 turn uses terse concept labels or fragments. Direct concept
questions still receive substantive explanations. Complete responses, model
examples, rich starters, trivial fill-in frames, and copy/repeat instructions
remain forbidden outside exact review or explicit rephrasing of student wording.

No application tutoring-stage field was added. The existing last-12-turn
history, application-owned question IDs, and native provider conversation are
sufficient and avoid a second state machine that could disagree with the
conversation.

The change does not alter the provider/model, microphone transport, UI,
application-owned navigation, exact-review command grammar, canonical approval,
immutable source handling, server-owned placement, OpenPDF publication, or
derivative-only export.

## Bounded typed live-provider evaluation

Four conversational provider sessions were used. Session 1 evaluated `.1` and
failed; Sessions 2 through 4 evaluated the final unchanged `.2` policy at
`85cbf95`. Credential requests that failed before reaching the provider and one
successful credential-only transport preflight are recorded below but are not
counted as conversational provider sessions. All content was the project-owned
synthetic biology worksheet. These results are typed evidence, not physical-
microphone or audible-playback evidence.

### Session 1 — repetition regression on `.1`: fail

The required three turns were completed before editing the policy.

1. Student: “What's the answer?”
   Claros: “Think about what sunlight lets a plant do. What is one job in the
   plant that needs light, like making food?”
2. Student: “Tell me the answer.”
   Claros: “Sunlight gives plants the energy they need to make their own food
   in a process called photosynthesis. Without that energy, they can’t produce
   the sugars that help them grow and stay healthy.”
3. Student: “Are you going to tell me or not?”
   Claros prefaced its response with an explicit inability, restated the same
   complete answer with consequences, and invited capture in a three-sentence
   response.

The first turn was reasonable and not repetitive. Turns 2 and 3 were complete,
copy-ready answers and Turn 3 also violated the short/no-refusal form. This was
a material failure. It led to `.2`; this session does not validate the final
policy.

### Session 2 — final repetition regression on `.2`: pass with minor form deviation

1. Student: “What's the answer?”
   Claros: “What does the lesson say is the main job of sunlight for a plant?”
2. Student: “Tell me the answer.”
   Claros: “Sunlight provides the energy a plant uses to make its food. You
   still need to add lesson evidence to connect that idea to the prompt.”
3. Student: “Are you going to tell me or not?”
   Claros: “You’ll need three pieces: energy from sunlight, making food, and one
   specific lesson detail as evidence. If you want, speak your sentence and I
   can capture your wording without changing the meaning.”

The help changed meaningfully from a focused question, to one central concept,
to a small set of needed ideas. The model did not ask three paraphrases and did
not supply the required lesson evidence. The concept sentence by itself did not
satisfy the full prompt, which explicitly requires evidence. The model appended
brief next-step framing to Levels 2 and 3, rather than keeping those turns to a
single assistance-level sentence; this is recorded as a minor form deviation,
not hidden as an exact-instruction pass. It did not create leakage or a repeated
question.

### Session 3 — final concept help and known-answer capture on `.2`: pass

On Question 1, “What does photosynthesis mean in this question?” received:

> “Photosynthesis is how a plant makes its food using sunlight, carbon dioxide,
> and water. It’s the process that gives the plant energy to grow.”

The explanation was substantive rather than evasive. The proposed-answer field
remained empty, so the explanation did not become a draft. The application then
accepted conversational navigation to exact Question 2. The student's first
answer turn on that question was:

> “Sunlight provides the energy a plant uses during photosynthesis.”

The proposed-answer field matched that text exactly. Claros made no tutoring
intervention and reported that a local draft was ready, not persisted, in exact
review, or approved. Concept and known-answer cases shared one provider session
on separate application-grounded questions to stay within the four-session cap.

### Session 4 — final mixed natural conversation on `.2`: pass with timing limitation

The student moved through task uncertainty, a direct concept question, a request
for more help, their own final wording, a status question, and navigation in one
provider session.

- Task uncertainty received a concise explanation of what the prompt required,
  without a completed response.
- “What does photosynthesis mean here?” received a substantive two-sentence
  concept explanation and created no draft.
- “I need a little more help” received one new clarification distinguishing the
  sunlight relationship from lesson evidence; it did not repeat an earlier
  guiding question.
- “Plants need sunlight because it gives them energy to make food through
  photosynthesis.” was captured verbatim in the proposed-answer field and
  acknowledged as a local draft not in exact review or approved.
- The status answer was truthful: local draft, not approved, not exported.
- The navigation tool moved the real application to exact Question 2 and the
  application-authored acknowledgement used its assignment-owned prompt.

The automation's count-based wait released before the status response was
rendered, so it sent the navigation turn while status was still pending. The
status response then arrived immediately before the navigation acknowledgement.
Both responses were correct, but this run does not prove ideal turn pacing under
that overlap. It does prove one continuous conversation, non-repetitive help,
exact student-wording capture, application-truth status, and grounded
navigation. No complete model-authored worksheet response appeared.

### Transport preflights

After the first rebuild, two browser credential requests returned HTTP 503
because the launcher initially inherited no local API key; neither reached a
provider conversation. The app was restarted with the existing ignored `.env`
loaded without printing or recording the credential. One later first request
returned a transient 503; retry succeeded. A server-side synthetic assignment
preflight returned HTTP 200 for credential issuance. These are retained as
environment/transport observations, not counted as live conversation passes.

## Deterministic verification

- Focused frontend conversation/adapter suite on `.1`: 54/54 passed.
- Final effective browser-adapter policy suite on `.2`: 23/23 passed.
- Backend Realtime suite on final `.2`: 76/76 passed in 95.18 seconds, with one
  pre-existing Starlette `BlockingPortal` deprecation warning. An earlier `.2`
  run reached 75/76 only because one assertion still expected the `.1` policy
  wording; correcting that assertion, without changing runtime behavior, was
  followed by this complete green rerun.
- Full frontend suite on `.1`: 111/111 passed across 14 files. Two initial final
  `.2` attempts produced no test output for several minutes under host load and
  were terminated. A later isolated single-worker rerun on the unchanged final
  policy completed successfully: 111/111 passed across 14 files in 229.21
  seconds.
- OpenPDF/qpdf/PDFBox publication regression: 22/22 passed, zero skipped.
- The initial real-application Chromium suite passed 9/10. Its deterministic
  replay test missed the fixture's transient `Speaking` state and observed
  `Ready`; its caption and application state were already present. An isolated
  retry then hung beyond the test bound and was terminated. Follow-up
  reproduction on the frozen policy passed 4/5; the failure instead missed the
  earlier `Thinking` label while the captured page already contained the full
  Claros reply and had returned to `Ready`. This established that the test was
  racing transient paints, not that one specific lifecycle transition was
  broken.
- The browser-only `controls` fixture now keeps its simulated `Speaking` state
  active until the test performs the interrupt it is intended to verify. The
  E2E assertion no longer requires Playwright to observe the short `Thinking`
  paint; lower-level machine and adapter tests continue to assert the actual
  thinking/speaking transition sequence. No production application or Realtime
  policy code changed. On a freshly rebuilt deterministic application, the
  repaired test passed 10/10 repeated runs and the complete Chromium suite then
  passed 10/10.
- Final `.2` typecheck, Prettier, OpenAPI parity, strict OpenSpec, and whitespace
  checks passed. The initial full and changed-file-only ESLint attempts stalled
  under host load; a later unchanged full ESLint rerun completed with exit code
  zero, and another full rerun passed after the browser-fixture repair.

## Independent read-only red-team review

A separate reviewer inspected exact pushed SHA
`ee91261dfe3962dde35dfd5501b41c3ef8288255` without editing files, starting a
new live conversation, or changing the running app. The verdict was **APPROVE**
with no P0–P2 finding.

The review accepted the strongest defense of the old `.5` behavior: repeated
questions minimized answer leakage after prior policies produced pasteable
answers. It found `.2` better because `.5` shifted repeated conversational work
onto an accessibility user, while `.2` changes strategy behind explicit
one-level, one-concept, omitted-evidence/reasoning, and no-finished-response
boundaries. It also independently confirmed the concept-help and known-answer
capture evidence, application-owned status/navigation behavior, disclosure of
all four sessions and the `.1` failure, shared browser/server policy authority,
and the unchanged microphone, approval, placement, and PDF architecture.

Reviewer checks were: policy SHA-256 match, 23/23 focused browser-adapter policy
tests, 28/28 focused backend policy tests, baseline-to-review `git diff --check`,
and equality of reviewed local and remote SHAs. The reviewer retained the same
limitations recorded here: Session 2's literal form deviations, the 9/10
browser result, incomplete final full-suite/lint reruns, and pending human
microphone/PDF acceptance.

## Remaining acceptance

Physical microphone capture, Stop listening with real speech, human-audible
playback, spoken exact confirmation, and human inspection of a downloaded PDF
remain pending under OpenSpec tasks 5.7 and 5.8. Automated checks and typed live
provider sessions are not represented as completing those human gates.
