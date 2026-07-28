# Revamp Stage 7 verification

## Scope and provenance

- Base SHA: `4f36afd` (`Merge pull request #25` — Stage 6 on `main`).
- Working branch: `codex/stage7-visual-design`.
- Scope: dedicated visual design audit and polish within the established Claros
  cool pale-blue academic direction. Landing uses Sort-style hierarchy/pacing.
  Worksheet behavior and accessibility contracts are unchanged.
- Contributor evidence: current Codex/Cursor task, visual audit, repository
  diff, frontend contract checks.

## Visual changes

| Surface | Change |
| --- | --- |
| Landing hero | Claros brand is the primary signal; headline secondary. |
| Hero media | Official Short Answer preview replaces synthetic `sample-workspace.png`. |
| Hero overlays | Floating `evidence-note` sticker removed; caption sits in flow. |
| Pacing | Larger section padding and restrained final CTA gradient. |
| Motion | Subtle rise animation with reduced-motion kill-switch. |
| App setup | Claros brand cue in product kicker. |
| App confirm/write | Stronger confirmation panel hierarchy; larger response-target hit area. |
| DESIGN.md | Synced to actual cool-blue tokens and brand-first landing rules. |

## Verified evidence

| Check | Result |
| --- | --- |
| Frontend contract | Passed (`python scripts/validate_frontend.py`) |
| Landing sample preview route | Uses `/samples/canonical-short-answer-ecosystems/preview.png` |

## Independent review / red-team findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| S7-P1-1 | P1 | Landing brand was nav-only; headline overpowered Claros. | Fixed: `.hero-brand`. |
| S7-P1-2 | P1 | Floating evidence-note overlay and synthetic workspace asset. | Fixed: in-flow caption + official preview. |
| S7-P2-1 | P2 | Checked-in `frontend/sample-workspace.png` remains for legacy route. | Deferred to Stage 10 cleanup; landing no longer depends on it. |
| S7-P2-2 | P2 | Deep visual QA at 390px / 200% zoom still benefits from Stage 8 pass. | Owned by Stage 8. |

No remaining valid P0 findings for Stage 7 acceptance.

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 7.
