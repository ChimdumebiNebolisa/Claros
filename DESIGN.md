# Design

Visual system for the Claros frontend (vanilla HTML/CSS/JS). Tokens live in
`frontend/styles/tokens.css`; page styles in `frontend/styles/landing.css` and
`frontend/styles/app.css`.

## Theme

Calm, precise, academic. Cool pale-blue paper surfaces with a restrained orange
accent and dark ink. The product should feel like a trustworthy worksheet desk,
not a dashboard or purple AI template.

## Color

| Role | Token | Value |
|---|---|---|
| Body background | `--bg` / `--bg-tint` / `--bg-blue` | `#f5f8fa` / `#eaf2f7` / `#dceef7` |
| Surface | `--surface` / `--surface-soft` | `#ffffff` / `#f8fbfd` |
| Ink (text) | `--ink` / `--ink-soft` / `--muted` | `#14232d` / `#314651` / `#617782` |
| Accent | `--iris` / `--iris-deep` / `--iris-soft` | `#df6c23` / `#ab4710` / `#fff0e4` |
| Dark counterpoint | `--dark-bg` / `--dark-surface` / `--dark-text` | reserved for rare contrast surfaces |
| Success / warn / error | `--success*` / `--warn*` / `--error*` | reserved for state only |

Primary buttons use dark ink on orange (`--on-accent` on `--iris`) or white on
deep orange so text contrast meets WCAG AA.

## Typography

System-native premium stack (`--font-sans`): Avenir Next → Segoe UI Variable →
system-ui. Weight and scale carry hierarchy. Landing brand/headings use
`clamp()`; the app uses a compact rem scale.

## Shape and elevation

Radii: 8 / 14 / 20 / 28 px + pill. Soft layered shadows
(`--shadow-soft/mid/strong`). Cards only where grouping or interaction needs a
container; prefer spacing and surface shifts elsewhere. Landing hero evidence
is a real worksheet preview, not a floating promo sticker.

## Motion

150–250 ms ease transitions; landing section rise at ~640 ms with staggered
delays. Global `prefers-reduced-motion` kill-switch in `tokens.css` and landing
styles.

## Application state vocabulary

Body attributes:

- `data-workspace-state`: `empty` | `uploading` | `parsing` | `ready` |
  `needs_layout_review` | `exporting` | `complete` | `error`
- `data-voice-state`: `unavailable` | `idle` | `connecting` | `listening` |
  `speaking` | `answer_detected` | `confirming` | `confirmed` | `writing` |
  `stopped` | `error`

Derived UI comes from `frontend/ui-state.js`.

## Landing page

Brand-first hero: Claros is the primary visual signal, followed by one headline,
one supporting sentence, and one CTA group beside a real sample-page preview.
Sort-style pacing uses generous section spacing and restrained decoration.
Worksheet behavior and accessibility contracts remain owned by the app shell.
