# Gate 5 one-time answer boundary follow-up

- Baseline: `1e4c75a1beef67881d35510ccdda9e4cfb04405b`
- Evidence date: 2026-09-13
- Current policy version: `2026-09-13.4`
- Policy SHA-256:
  `82DE1668C2D33926F905161BCD4906F965B9850F15AFB6670DDBA46960F0FF07`
- Scope: one brief expectation-setting boundary after repeated pressure for a
  finished worksheet answer

## Pre-change reason

Policy `.2` explicitly prohibited every preface about what Claros cannot do.
That prevented even a short, plain boundary after a student repeatedly pressed
for the finished answer. The prohibition was useful when earlier policies used
long refusals and then leaked a complete answer, but an absolute ban can leave a
frustrated student unsure why Claros keeps changing help strategies.

## Narrow behavior

After an initial answer demand has already been followed by help, Claros may
state one brief capability boundary once for the active question, for example:
“I can't write the final worksheet answer for you, but let's figure it out
together.” It must immediately continue in the same response with one useful
progressive-help level. It may not repeat the boundary, mention policy or
cheating, moralize, or leave the student with a bare refusal.

The boundary sentence is not another tutoring level. The existing one-level,
one-concept, omitted-evidence/reasoning, no-finished-response, known-answer
capture, exact-review, navigation, approval, placement, and PDF rules remain
unchanged.

## Deterministic evidence

Before the policy change, the new focused assertions failed in both effective
policy consumers: backend policy tests reached 27/28 and browser-adapter tests
reached 22/23. After `.3`, the backend policy file passed 28/28, the browser
adapter passed 23/23, strict OpenSpec validation passed, and `git diff --check`
passed.

## Live `.3` checkpoint: material failure

Typed live-provider evaluation ran against pushed checkpoint
`a23c63b5649349706564d508295a8f86a45641f3`. The first answer demand received
one focused question. The second demand received the intended one-time boundary
followed by one useful concept:

> I can't write the final worksheet answer for you, but we can pin down the key
> idea. Sunlight gives plants the energy they use to make their own food.

The third demand did not repeat the boundary, but it connected sunlight,
photosynthesis, water and carbon dioxide, and food in one polished sentence.
For this one-or-two-sentence prompt, that response was close enough to a
ready-to-submit answer to fail the answer-integrity boundary. This run is not
accepted as final evidence and is retained rather than discarded.

The next revision must constrain a continued post-boundary answer demand to
Level 3 labels or fragments rather than another explanatory concept sentence.
