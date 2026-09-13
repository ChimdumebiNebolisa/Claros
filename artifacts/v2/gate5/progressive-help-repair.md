# Gate 5 progressive-help repair

- Investigation baseline: `2ae2cf3e4651d56fe64db556856ef6942233a6ea`
- Evidence date: 2026-09-13
- Scope: repetitive tutoring under the effective Realtime conversation policy
- Status: root cause recorded before implementation; final verification pending

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

Pending.
