# Revamp Stage 8 verification

## Scope and provenance

- Base SHA: `a95c936` (`Merge pull request #26` — Stage 7 on `main`).
- Working branch: `codex/stage8-mobile-a11y`.
- Scope: mobile and accessibility — keyboard/typed fallback, screen-reader
  semantics, touch targets, true fit-width, and a mobile dock that does not hide
  core typed flows. No Stage 9 voice transport rewrite.
- Contributor evidence: current Codex/Cursor task, a11y audit, independent
  red-team pass, repository diff, frontend contract checks, worksheet-view
  regression tests.

## Accessibility and mobile changes

| Area | Change |
| --- | --- |
| Mobile dock | Collapsed panel keeps question context, typed draft, notices, and mic-denial fallback visible. |
| Mic denial | Voice fallback expands the panel and focuses the typed draft. |
| Workspace errors | Visible `#workspaceErrors` alert; failures also mirror into dock `#notice` when ready. |
| Fit width | Document page no longer forces 34rem/30rem min-width; Fit width sets container-scale 100% and tracks `aria-pressed`. |
| Worksheet clearance | Mobile document scroll reserves bottom space sized to the fixed sheet; expands further when the panel is open. |
| Semantic task | Task excerpt beside the visual worksheet; choices expand with the panel. |
| Choices | Choice controls fill the draft for review; they do not confirm or write. |
| Touch targets | Primary toolbar, export, choice, confirm/write, and typed-confirm controls use ≥44px min-height. |
| Focus | Reject/dismiss restores focus to the typed draft; return-to-worksheet restores the document viewport. |
| Live regions | Task progress/placement no longer force polite status live regions; status/error/notice remain. |
| Reduced motion | Existing global reduced-motion kill-switch retained. |

## Verified evidence

| Check | Result |
| --- | --- |
| Frontend contract | `python scripts/validate_frontend.py` |
| Worksheet target/fit-width tests | `npm run test:worksheet-targets` |
| Worksheet security text escaping | `npm run test:worksheet-security` |
| Independent red-team | Fresh review session; P1 dock clearance and sticky-mic overlap fixed before merge |

Full device/AT matrix (NVDA/VoiceOver/200% zoom keyboard tour) remains Stage 14.

## Independent review / red-team findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| S8-P0-1 | P0 | Collapsed mobile dock hid typed answer and mic-denial fallback. | Fixed: allowlist + taller collapsed sheet. |
| S8-P0-2 | P0 | Workspace errors only rendered inside hidden setup `#errors`. | Fixed: `#workspaceErrors` + notice mirror. |
| S8-P0-3 | P0 | Fit width was a no-op over forced `min-width: 34rem`. | Fixed: min-width 0 + fit-width mode. |
| S8-RT-01 | P1 | Document bottom padding was smaller than dock height. | Fixed: `max(24rem, 52dvh)` clearance; larger when expanded. |
| S8-RT-02 | P1 | Sticky mic covered typed confirm in collapsed sheet. | Fixed: absolute mic corner + panel bottom padding; hide choices until expand. |
| S8-P1-1 | P1 | MC choices were non-interactive text. | Fixed: choice buttons seed draft only. |
| S8-RT-04 | P2 | Live-region noise from placement/progress. | Fixed: dropped `role="status"` on those nodes. |
| S8-RT-05 | P2 | Some controls under 44px. | Fixed: confirm/export min-height 2.75rem. |
| S8-RT-09 | P3 | No `inert`/`aria-modal` on expanded sheet. | Accepted; owned by Stage 14. |
| S8-P2-1 | P2 | Full AT browser matrix still benefits from Stage 14 audit. | Owned by Stage 14. |
| S8-P2-2 | P2 | Monolithic `app.js` / orphan modules remain. | Owned by Stage 10. |

No remaining valid P0/P1 findings for Stage 8 acceptance after the red-team remediation pass.

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 8.
