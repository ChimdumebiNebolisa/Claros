## Purpose

Defines one adaptive voice conversation, captions, constrained Realtime
authority, exact-state voice confirmation, and typed recovery without data loss.

## ADDED Requirements

### Requirement: Authorized short-lived Realtime sessions
The browser MUST connect to OpenAI Realtime over WebRTC using a short-lived
credential issued only after the server validates owner, assignment, active
question and assignment version. A standard provider API key
MUST never reach the browser.

#### Scenario: Authorized student starts voice
- **WHEN** the active assignment, question, version, and owner all match
- **THEN** Claros issues a short-lived client credential and the browser may open that bounded Realtime session

#### Scenario: Context is stale
- **WHEN** the requested question or assignment version is no longer active
- **THEN** credential issuance fails safely and no provider credential is returned

### Requirement: Explicit accessible voice controls and states
Voice UI MUST expose Ready, Listening, Thinking, Speaking, Interrupted,
Connection lost, and Microphone unavailable as text. It MUST provide start,
stop capture, interrupt output, speaker mute/unmute, live captions, retry, and
`Continue by typing`. Capture and playback MUST remain independently controllable,
and Listening MUST be shown only while microphone capture is active.
A waveform or color MUST never be the sole state indicator.

#### Scenario: Claros begins speaking
- **WHEN** a Realtime response produces audio
- **THEN** the UI displays `Speaking`, exposes an interrupt and mute control, and keeps matching text available

### Requirement: One agent adapts to conversational intent
The agent MUST infer whether a turn requests answer capture, concise help,
revision, or grounded question navigation. It MUST minimize interruption when
capturing a known answer, offer concise grounded help when requested, and ask a
short clarification when intent is ambiguous. It MUST NOT introduce a
materially new fact or make a fragment more complete without student choice.

#### Scenario: Student provides a complete direct answer
- **WHEN** the captured turn contains a usable answer
- **THEN** Claros creates one student-derived candidate and moves toward review without adding substantive content

The conversation MUST remain grounded in the exact active question and allowed
source context, ask one focused question at a time when help is wanted, avoid
unsolicited lectures, and stop tutoring when the student intends an answer.
Discussion and command turns MUST NOT become the candidate automatically.

#### Scenario: Student moves from help to an intended answer
- **WHEN** the student indicates readiness and then states a final response
- **THEN** Claros creates a `student_after_guidance` candidate from that response and enters the normal review flow

#### Scenario: Transcript exists without final response
- **WHEN** conversation turns contain ideas but the student has not stated a final answer
- **THEN** no candidate is eligible for review or confirmation solely from the transcript

### Requirement: Application-owned turn and draft relationships
Completed transcription events MUST carry application-observed session and turn
identity. The application, not the model, MUST bind an intended draft to the
matching completed student turns and current question. The model MUST NOT be
required to guess or return private source-turn identifiers.

#### Scenario: Model proposes an answer draft
- **WHEN** the model requests a draft from student-intended answer text
- **THEN** the adapter binds it to matching completed student turns and rejects unknown or materially changed text

### Requirement: Narrow Realtime authority
Realtime MAY request active question context, set a student-derived candidate
with source-turn evidence, request clearer wording, enter exact review, or
report a voice issue. It MUST NOT approve for the student, select or alter
geometry, rewrite source questions, choose an arbitrary question, export, or
write a PDF. Every product mutation MUST pass the normal authenticated API and
version checks.

#### Scenario: Voice tool requests PDF write
- **WHEN** a model emits a tool name or payload outside the permitted schema
- **THEN** the adapter rejects it without changing candidate, answer, placement, or export state

### Requirement: Exact-state voice confirmation
Voice confirmation MUST invoke the same server confirmation operation as the
button and MUST be accepted only while exact review is active and the student
uses the canonical phrase `Use this exact answer`. Casual agreement or the
phrase in any other state MUST NOT confirm.

#### Scenario: Exact phrase is spoken during review
- **WHEN** the active fresh review matches the candidate and the canonical phrase is recognized
- **THEN** Claros submits the bound confirmation request through the normal authenticated path

#### Scenario: Student says yes during tutoring
- **WHEN** `yes`, `okay`, or another casual agreement is spoken outside exact review
- **THEN** no confirmation request is created and the conversation continues in its current state

### Requirement: Voice failure preserves progress
On permission denial, connection failure, or audio failure, Claros MUST preserve
the current candidate and bounded relevant turns, attempt at most one automatic
reconnect, expose `Retry voice` and `Continue by typing`, and avoid duplicate
candidates from replayed events. It MUST never require worksheet re-upload.

Interrupting output MUST NOT destroy a healthy session. A necessary reconnect
MUST preserve and replay bounded application-owned conversation context.

#### Scenario: Realtime disconnects after a draft
- **WHEN** voice connectivity fails with candidate text present
- **THEN** the same exact text remains editable and the student can complete review and confirmation by typing and keyboard

#### Scenario: Replayed transcript event arrives
- **WHEN** a reconnect repeats an already processed event identity
- **THEN** Claros ignores the duplicate and retains one candidate revision

### Requirement: Exact answer playback is optional assistance
The exact-review state MUST offer `Hear it` to speak the displayed candidate on
demand. Playback failure or unavailability MUST NOT prevent button or keyboard
confirmation of the visible exact text.

#### Scenario: Playback is unavailable
- **WHEN** the student activates `Hear it` but audio output fails
- **THEN** the exact text remains visible and `Use this exact answer` remains available
