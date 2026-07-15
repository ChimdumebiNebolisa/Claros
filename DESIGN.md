# Design

Visual system for the Claros frontend (vanilla HTML/CSS/JS). Tokens live in `frontend/styles/tokens.css`; page styles in `frontend/styles/landing.css` and `frontend/styles/app.css`.

## Theme

Calm, precise, academic. Warm neutral paper surfaces with a restrained orange accent and dark ink. The product should feel like a trustworthy worksheet desk, not a dashboard or purple AI template.

## Color

| Role | Token | Value |
|---|---|---|
| Body background | `--bg` / `--bg-tint` / `--bg-blue` | `#f4f4f2` / `#ecece8` / `#e8e8e4` |
| Surface | `--surface` / `--surface-soft` | `#ffffff` / `#f8f8f6` |
| Ink (text) | `--ink` / `--ink-soft` / `--muted` | `#17120d` / `#383632` / `#5c5953` |
| Accent | `--iris` / `--iris-deep` / `--iris-soft` | `#f97316` / `#c2410c` / `#fff0e3` |
| Dark counterpoint | `--dark-bg` / `--dark-surface` / `--dark-text` | `#11110f` / `#1c1b18` / `#f8efe4` |
| Success / warn / error | `--success*` / `--warn*` / `--error*` | reserved for state only |

Primary buttons use dark ink on orange (`--ink` on `--iris`) or white on deep orange (`--iris-deep`) so text contrast meets WCAG AA.

## Typography

System-native premium stack (`--font-sans`): Avenir Next → Segoe UI Variable → Seravek → system-ui. Weight and scale carry hierarchy. Landing headings use `clamp()`; the app uses a compact rem scale.

## Shape and elevation

Radii: 10 / 14 / 20 / 28 px + pill. Soft layered shadows (`--shadow-soft/mid/strong`). Cards only where grouping or interaction needs a container; prefer spacing and surface shifts elsewhere.

## Motion

150–250 ms ease transitions; status pulses only for live voice feedback. Global `prefers-reduced-motion` kill-switch in `tokens.css`.

## Application state vocabulary

Body attributes:

- `data-workspace-state`: `empty` | `uploading` | `parsing` | `ready` | `needs_layout_review` | `exporting` | `complete` | `error`
- `data-voice-state`: `unavailable` | `idle` | `connecting` | `listening` | `speaking` | `answer_detected` | `confirming` | `writing` | `stopped` | `error`

Derived UI comes from `frontend/ui-state.js`. Labels, badges, disabled reasons, confirmation visibility, and export labels must not be hard-coded in scattered `app.js` branches.

Key DOM contracts:

- Setup: `#setupMode`, `#uploadZone`, `#processingPanel`
- Workspace: `#workspaceMode`, `#documentViewport`, `#pageImage`, `#answerOverlayLayer`
- Voice: `#sessionPanel`, `#voiceBadge`, `#status`, `#answerConfirmation`, `#micBtn`, `#interruptBtn`
- Live regions: `#workspaceStatus`, `#status`, `#notice`, `#errors`

Mobile dock: below ~768px, `#sessionPanel` becomes a fixed bottom dock. Confirmation and writing states auto-expand the dock.

## Document canvas

`frontend/worksheet-view.js` maps manifest `answer_region` percentages onto the rendered page PNG. Layout correction is an advanced recovery mode: enter only when `needs_layout_review` is true.

## Landing page

Asymmetric hero with the product headline, short support copy, primary/secondary CTAs (`Start a worksheet` / `Try the sample`), then a separate trust strip. Product scenes should reflect the real document workspace, not a fabricated question-card UI.

## Manual verification notes

Automated tests cover contracts and sample region reliability. Native browser 200% zoom, screen-reader passes, and real Gemini Live sessions remain manual or environment-gated checks.
