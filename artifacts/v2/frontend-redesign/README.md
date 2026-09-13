# Claros frontend redesign evidence

Captured on 2026-09-13 for `codex/claros-v2-nerdy`.

## Baseline

The baseline was commit `cea7ee164a137d7c7cec2f0016632be2070bc9c0`. It had a two-column marketing hero dominated by an application mockup, two oversized mode-like cards, hidden mobile navigation, a fragmented conversation/voice/message/draft stack, and an Untitled UI layer that duplicated the visual system used by the current V2 surfaces.

`before/` contains the previously checked-in app state matrix plus newly captured marketing tablet evidence from a detached baseline worktree. No baseline source files were modified.

## Final direction

The redesigned product uses an editorial marketing surface and a compact, task-first application workspace. Instrument Serif carries marketing display typography; Inter remains the application face. A small Claros-owned open-code primitive layer, Tailwind composition, Lucide icons, Radix Dialog, Motion, and the existing EmbedPDF viewer replace the former visible Untitled foundation.

The defining application relationship is deliberately explicit:

1. Conversation is one coherent voice/text interaction surface.
2. The proposed answer remains a separate, editable, question-scoped object.
3. Exact review is promoted above the folded transcript.
4. Only the unmistakable approval action can place the exact wording.
5. The source worksheet remains visible on desktop and opens as a task-first dialog on mobile.

## Open-code references

| Source | Use | Integration |
| --- | --- | --- |
| [21st.dev Hero 24](https://21st.dev/@ln-dev7/components/hero-24) | Centered, typography-led hero with one action | Composition adapted and reimplemented in Claros; no registry package installed |
| [21st.dev How It Works 01](https://21st.dev/@ln-dev7/components/how-it-works-01) | Continuous numbered process | Semantic structure adapted and reimplemented in Claros |
| [21st.dev Efferd CTA 3](https://21st.dev/@efferd/components/cta-3) | One statement and one action | Principle used as inspiration only |
| [Beautiful UI Chat / ChatComposer](https://www.beautifului.dev/) | Unified conversation surface | Interaction hierarchy adapted to existing Claros state and handlers; demo state was not copied |
| [Beautiful UI Prompt Bar](https://www.beautifului.dev/) | Integrated microphone, status, text entry, and send controls | Composition adapted and simplified; model/source/attachment/demo features omitted |
| [Beautiful UI Approval Card](https://www.beautifului.dev/) | Compact human-in-the-loop decision hierarchy | Visual hierarchy adapted; Claros server review and confirmation authority retained |
| [Beautiful UI Loading State](https://www.beautifului.dev/) | Restrained indeterminate analysis feedback | Pattern adapted without fake progress, reasoning, or stages |

The referenced projects publish open code under MIT-compatible terms. No 21st.dev or Beautiful UI runtime dependency was added, and no demo product logic, `glimm`, model picker, source picker, or local approval carousel entered the application.

## Migration record

- `components.json` was deliberately converted to the Claros shadcn-style open-code registry configuration. `shadcn init` was not run, avoiding an accidental overwrite of the prior registry configuration.
- Claros-owned `Button`, `Textarea`, and loading primitives were added under `src/v2/ui` and tailored to existing handlers and accessibility semantics.
- The visible V2 dialog moved to Radix Dialog. The legacy `src/components/ui` path remains isolated for `/legacy`.
- Twenty-six unused Untitled component files, the V2 marketing CSS module, Untitled packages/icons, and unused React Aria packages were removed after typechecking the migrated surfaces.
- `react-dropzone` remains because the isolated legacy workspace still imports it.
- Authored V2 CSS changed from 834 baseline lines (`v2.css` plus the marketing module) to 462 global/special-purpose lines. Ordinary marketing and workspace layout now lives in Tailwind/component composition; PDF and specialized answer/voice styling remains in CSS modules where appropriate.

## Capture matrix

`after/manifest.json` records 49 state/viewport images, SHA-256 hashes, the implementation commit, and confirms that the capture made no external requests. It covers:

- marketing at 1440px, 1024px, 768px, and 390px;
- upload, checking, ready, unsupported, and voice-unavailable states;
- empty, listening, multi-turn, and populated-draft conversation states;
- exact inline and appendix review;
- answer placement, worksheet review, and export completion;
- mobile source worksheet dialog with the actual rendered PDF;
- 768px compact-tablet evidence for conversation and exact review;
- 1024px structural states for question choice, conversation, guided help, and worksheet review.

The baseline and after directories are intentionally retained as release evidence. Production-route spot captures are also retained where they prove the fixture presentation matches the running application.

## Visual review

Side-by-side review found materially stronger hierarchy, typography, spacing rhythm, CTA focus, conversation readability, draft distinction, approval prominence, worksheet context, and mobile composition. The final surfaces use the Claros worksheet-margin line, restrained cobalt emphasis, cool paper/canvas surfaces, semantic green/amber, compact radii, and minimal shadows rather than generic registry defaults.

Automated verification and the independent read-only review are recorded in the
[final implementation report](IMPLEMENTATION_REPORT.md).
