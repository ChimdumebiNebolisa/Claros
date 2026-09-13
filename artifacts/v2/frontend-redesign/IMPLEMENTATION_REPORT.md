# Claros frontend redesign implementation report

- **Branch:** `codex/claros-v2-nerdy`
- **Baseline:** `cea7ee164a137d7c7cec2f0016632be2070bc9c0`
- **Feature implementation checkpoint:** `42574782016a8c870c0943eaf3d3f8a39baff807`
- **Corrected implementation checkpoint:** `fec63d2ae5a1535e41fb9b70078840e5f29bb0e4`
- **Independent review:** first pass closed authority/evidence/debris findings;
  second pass requested exact-review DOM ordering; final-candidate review pending
- **Date:** 2026-09-13

## Outcome

The redesign replaces a fragmented, card-heavy frontend with one Claros-specific
visual system. Marketing is now editorial and typography-led. The application is
task-first, keeps the real worksheet visibly present, makes voice the easiest path
without hiding typing, separates conversation from the editable proposed answer,
and promotes exact approval above secondary transcript detail.

The baseline problems were an application screenshot dominating the marketing
hero, two oversized cards that implied two answer modes, missing mobile navigation,
an oversized standalone voice card, competing conversation/message/draft surfaces,
weak exact-review priority, and a generated Untitled layer competing with current
V2 styling.

## Open-code source use

| Source | Classification | Result |
| --- | --- | --- |
| 21st.dev Hero 24 | Adapted and reimplemented; not registry-installed | Centered, typography-led hero with one primary action and no application mockup |
| 21st.dev How It Works 01 | Adapted and reimplemented | One semantic ordered sequence from speaking through completed PDF |
| 21st.dev Efferd CTA 3 | Inspiration-only | One closing statement and one action |
| Beautiful UI Chat / ChatComposer | Interaction hierarchy adapted | One bounded conversation with an integrated voice/text composer wired to existing handlers |
| Beautiful UI Prompt Bar | Adapted and simplified | Microphone, written voice state, text entry, send, interrupt, and speaker mute; demo features removed |
| Beautiful UI Approval Card | Hierarchy adapted | Compact exact-review surface controlled by Claros server review and confirmation authority |
| Beautiful UI Loading State | Indeterminate pattern adapted | Honest worksheet checking feedback with no fake percentage, reasoning, or stage |

No registry runtime package, demo state, model picker, source picker, local approval
carousel, shader, or `glimm` dependency entered the application.

## Foundation and migration

`components.json` was deliberately converted to a Claros shadcn-style open-code
configuration. `shadcn init` was not run, avoiding an accidental overwrite. The
small owned layer under `src/v2/ui` contains `Button`, `Textarea`, `LoadingState`,
and class composition. Tailwind handles ordinary layout, Lucide is the sole current
icon family, Radix provides the accessible dialog primitive, Motion remains the
single animation library, and EmbedPDF remains the authentic source renderer.

Untitled no longer remains in V2 source or dependencies. Twenty-six obsolete
Untitled files were removed after import, type, build, and browser proof. Historical
Gate 1 records remain explicitly labeled as superseded rather than being rewritten
as if the migration never occurred. React-PDF, dropzone, and resizable panels remain
only because `/legacy` still imports them; Gate 6 owns their removal.

Added library:

- `@fontsource/instrument-serif@5.3.0`

Removed libraries:

- `@untitledui/file-icons`
- `@untitledui/icons`
- `react-aria`
- `react-aria-components`
- `tailwindcss-animate`
- `tailwindcss-react-aria-components`
- `tw-animate-css`

## Visual and CSS architecture

Instrument Serif is locally bundled for marketing display text; Inter remains the
application and control face. The browser surface now includes a Claros `C` SVG
favicon, a product-specific title, and matching theme color.

Before, ordinary presentation was split across global Tailwind aliases, 424 lines
of `v2.css`, and 410 lines of marketing-module layout. After, the marketing module
is removed, ordinary composition lives beside components in Tailwind, specialized
PDF/voice/answer styling remains in focused CSS, `v2.css` is 462 lines, and the
Tailwind theme is 19 lines of used typography tokens. Unused generated alias and
animation-plugin vocabulary was removed after repository-wide usage checks.

## Product surfaces

- **Marketing:** screenshot-led two-column hero and two mode-like cards became a
  centered editorial hero, one CTA, an intentional mobile menu, a four-step process,
  student-control and accessibility sections, subordinate compatibility copy, one
  closing CTA, and a minimal footer.
- **Workspace:** separate voice/message/draft cards became one coherent bounded
  conversation and composer followed by a distinct question-scoped proposed answer.
- **Voice:** existing capture, stop, interrupt, and independent speaker-mute handlers
  are integrated into the composer with explicit written states. Typed fallback is
  continuously visible.
- **Exact review:** provenance, exact candidate text, `Hear it`, destination status,
  `Change answer`, and the dominant `Use this exact answer` action remain intact and
  are promoted ahead of collapsed conversation detail.
- **Source:** the real worksheet stays secondary but visible on desktop and opens in
  a task-first, keyboard-safe full-screen dialog on mobile. Source readiness is
  reported only when the authentic viewer is ready.

## Responsive and accessibility evidence

The checked-in `before/` and `after/` directories cover marketing and application
states at 390, 768, 1024, and 1440 pixels, including empty/listening/multi-turn
conversation, populated draft, inline/appendix exact review, answer placement,
worksheet review, completion, and the authentic mobile PDF viewer. The after
manifest records 49 images, SHA-256 hashes, and zero external requests.

Keyboard checks cover upload, dialog focus restoration, the mobile menu, voice
controls, review, and export. Automated axe found zero V2 Storybook violations.
Meaningful targets remain at least 44 pixels, written states do not rely on color,
reduced motion is respected, and measured pages had no horizontal overflow at 390,
720 (the 200-percent desktop equivalent), 768, 1024, or 1440 pixels.

## Verification

The feature checkpoint passed:

- `npm run ci`: format, lint, typecheck, dependency/license checks, 112 Vitest tests,
  Storybook build, Storybook axe, production build, and bundle boundaries;
- `npm run test:conversation`: 54/54 tests;
- `npm run test:e2e`: 10/10 Chromium tests;
- `npm run test:e2e:gate3`: restart persistence and partial export;
- `npm run check:visual`: existing baseline matrix;
- redesigned 49-image capture and responsive overflow/menu checks;
- `openspec validate claros-reconstruction --strict`;
- `npm audit --audit-level=high`: zero vulnerabilities.

The corrected implementation repeated the complete `npm run ci`, full browser,
visual-check, 49-image capture, dependency audit, and strict OpenSpec verification
after moving exact review before the secondary transcript in visual, DOM, keyboard,
and screen-reader order. A focused regression test covers the review-plus-transcript
state. The tool host uses Node 24 and therefore prints an engine warning; the
project targets Node 22, and its dependency verifier checks that declared target.

## Authority and semantic boundary

The execution PRD, product contract, design authority, engineering guide, conflict
and decision registers, risk register, and active OpenSpec tasks now describe the
proved open-code foundation and typography-led hero. This correction does not alter
the one adaptive conversation, student-authored/question-scoped draft ownership,
progressive-help policy, exact approval, application-owned navigation, immutable
source handling, deterministic placement, derivative-only export, or backend/API
authority.

Nothing was merged or deployed. The normal local application is rebuilt and served
at `http://127.0.0.1:8080/` and `http://127.0.0.1:8080/app` after final verification.
