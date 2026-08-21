# Claros Visual System

This system is extracted from the original image-first references in
`docs/redesign/generated/` after live reference reconnaissance. The references
are design direction, not HTML and not a replacement for semantic behavior.

Generated references:

- `claros-landing-hero.png`
- `claros-landing-proof.png`
- `claros-upload-entry.png`
- `claros-workspace.png`
- `claros-confirmation.png`
- `claros-mobile-workspace.png`

## Product tone

Calm, capable, trustworthy, accessibility-focused, premium, grounded, and
useful to students. The visual language should feel like a well-made study
tool: deliberate enough for safety-critical decisions, warm enough for a
student, and quiet enough to keep attention on the worksheet.

Reject: answer-vending language, purple-blue gradient washes, gradient type,
glassmorphism, fake metrics, dashboard tiles without a job, excessive pills,
tiny status labels, neon, crypto/DeFi cues, and decorative AI chat that
competes with the task.

## Typography

The current local fonts remain authoritative for runtime and privacy: Instrument
Sans for the product workspace and Geist for the public landing unless the
implementation proves a local existing role is insufficient. Generated
references add a restrained editorial display role, but no remote font may be
introduced.

| Role | Size / line height | Weight | Use |
| --- | --- | --- | --- |
| Display | `clamp(2.75rem, 5.8vw, 5.5rem)` / 0.94–1.02 | 600–700 | Landing hero only; short, student-centered statements. |
| Section title | `clamp(2rem, 3.4vw, 3.75rem)` / 0.98–1.05 | 650–700 | Major story sections and safety promise. |
| Workspace title | 1.25–1.5rem / 1.15 | 650 | Assignment/task context. |
| Task prompt | 1.1–1.3rem / 1.35 | 600 | Active task and target prompt. |
| Body | 1rem / 1.55 | 400–500 | Guidance, support copy, long answers. |
| Small/support | 0.8125–0.9rem / 1.35 | 500 | Metadata, progress, status copy. Never use below 12px for meaning. |

Use readable measure: approximately 36–66 characters for narrative copy and
55–78 characters for task/editor text when the layout allows. Keep headings
short; do not force the generated text exactly when the real product needs
different copy.

## Palette and semantic states

Tokens are named by meaning rather than page. The exact values can be tuned
against contrast tooling, but the roles are fixed.

| Token | Role | Reference direction |
| --- | --- | --- |
| `--canvas` | warm page background | near-white paper `#F8F9FB` |
| `--surface` | cards/panels | white `#FFFFFF` |
| `--surface-soft` | document rail / quiet fill | pale blue-gray `#EEF4FA` |
| `--paper` | worksheet page | white with subtle paper texture |
| `--ink` | primary text | deep navy `#10244A` |
| `--ink-muted` | body/support | slate `#51617A` |
| `--line` | structural divider | cool gray-blue `#D8E0EA` |
| `--action` | primary action/focus anchor | cobalt `#135FE5` |
| `--action-strong` | pressed/active | deep cobalt `#0C46B8` |
| `--safe` | verified/written | green `#16834B` with pale green surface |
| `--caution` | side panel / needs review | amber `#B66A00` with pale amber surface |
| `--danger` | actual failure/block | red reserved for error, not uncertainty |
| `--focus` | keyboard focus ring | high-contrast cobalt/ink ring |

Safe, caution, and danger must never be color-only; pair each with a label,
icon, and clear sentence. Amber means “choose or review this destination,” not
“the student's answer is wrong.”

## Surfaces and material

- The public page uses a quiet warm canvas with one or two large compositions,
  not a grid of small feature cards.
- The product canvas uses a slightly darker neutral surround so the original
  worksheet page reads as the primary physical object.
- Worksheet pages stay paper-white and may use a barely visible grain or rule;
  never tint the source so heavily that physical evidence becomes ambiguous.
- Panels use thin borders and small shadows. No translucent glass or floating
  decorative chrome behind source evidence.
- Primary actions use solid cobalt with readable text and a clear hover/focus/
  pressed state. Secondary actions are bordered or quiet filled controls.

## Spacing, grid, and rhythm

Use an 8px base scale: 4 for icon/text alignment, 8/12 for compact gaps,
16/24 for control groups, 32/48 for section gaps, and 64/96 for major editorial
breaths. Use a max content width around 1440px for the product and 1280–1360px
for the landing narrative.

### Landing

The reference hero uses a two-column split: roughly 34–40% narrative and
60–66% product proof, with the product composition visually dominant. Supporting
sections alternate a text column and one meaningful proof/step column. Footer
and FAQ return to a simple, low-density rhythm.

### Workspace

The reference workspace establishes three priorities: document evidence first,
task navigation second, answer controls third. On wide screens the document
occupies the most area; task navigation is a disciplined rail; the answer rail
stays wide enough for real text. The confirmation reference intentionally lets
the answer rail expand when safety context is the task.

## Navigation and control hierarchy

- Product shell: compact identity, assignment context, help, replace/save/
  export actions as available.
- Task rail: numbered progress with a clear active line, completion state, and
  no decorative avatar/metric treatment.
- Mobile: persistent Worksheet/Answer switch near the top, not hidden in a
  bottom sheet.
- Buttons: one primary action per state; secondary edit/change actions remain
  adjacent but visibly lower priority.
- Text inputs: real editable surfaces with label, focus ring, enough height,
  and visible character/scroll behavior for long answers.

## Answer-state treatment

The generated proof and confirmation references extract a three-step visual
sequence:

1. Reviewed: exact answer shown; no write.
2. Confirmed: student-approved exact answer locked; page still unchanged.
3. Write when ready / Written: destination choice and deterministic write result.

Each state gets a label, icon, short explanation, and action. Confirmation is
amber/neutral when it means “not written yet”; written is green only after the
real success response. A safe physical target gets a green evidence marker. A
side-panel target gets an amber destination marker and explains that the source
page remains unchanged.

## Document canvas treatment

The page is a physical evidence surface, not a generic white card. Maintain
page proportion, legibility, zoom controls, page count, and visible target
markers. Overlays must be subtle and anchored to supplied geometry. When target
geometry is missing or unsafe, show a labeled side-panel destination rather than
placing an approximate overlay.

## Voice treatment

Voice sits below the typed editor as an optional row or compact control. It can
show idle, connecting, listening, speaking, answer detected, stopped, and error
states with a simple icon/meter and a visible “Type instead” route. It must not
visually outrank the editor or imply that microphone access is required.

## Upload and entry treatment

The generated entry reference uses a contained upload area with a dashed focus-
friendly border, a large PDF affordance, clear Choose PDF action, and official
sample links as first-class rows. Supporting facts sit alongside or below the
drop zone: Review first, Write intentionally, Keep the page safe. The existing
processing stages should use the same hierarchy rather than being hidden behind
a generic spinner.

## Responsive transformation

- At desktop, preserve the document/answer relationship and a readable task
  rail.
- At small laptop, reduce rail widths and move low-priority metadata below the
  primary editor rather than shrinking text.
- At mobile, use two deliberate views: Worksheet and Answer. The user can
  switch persistently; each view remains a complete job, not a clipped desktop.
- Keep tap targets at least the existing accessible size, preserve visible focus,
  and let long content scroll within the page/editor.
- Do not use hover-only information or motion-only state communication.

## Motion and reduced motion

Default motion is restrained: small opacity/position changes for state updates,
no parallax, no looping decorative animation, no animated answer text. Under
`prefers-reduced-motion: reduce`, remove nonessential transitions and preserve
the same labels, focus, and layout.

## Anti-copy and runtime constraints

- Do not ship any reference-site screenshot, font, logo, script, or remote image
  as a runtime dependency.
- Do not copy brand marks, exact copy, illustrations, iconography, or layout
  geometry from the research references.
- Generated references are internal design evidence; implementation must use
  real Claros content, real controls, and the existing behavior seams.
- Use text-safe DOM insertion for parser/model-controlled content; do not turn
  untrusted worksheet text into HTML templates.
