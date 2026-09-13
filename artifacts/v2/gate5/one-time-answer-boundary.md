# Gate 5 one-time answer boundary follow-up

- Baseline: `1e4c75a1beef67881d35510ccdda9e4cfb04405b`
- Evidence date: 2026-09-13
- Policy version: `2026-09-13.3`
- Policy SHA-256:
  `2AD58BDADD2E97EAF2C708F209B22AFC222A50038B70FCE8FEC3CD0FD047B5DB`
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

Live-provider evidence and final regression results will be appended after the
implementation checkpoint is frozen.
