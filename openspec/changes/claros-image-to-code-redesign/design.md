## Context

The baseline serves static `frontend/landing.html` and `frontend/app.html` from
FastAPI. The worksheet workflow is orchestrated by `frontend/app.js` with stable
state/rendering seams in `ui-state.js`, `session-rules.js`, and
`worksheet-view.js`; voice is isolated in the bridge and transport modules.
The current backend already owns assignment manifests, server sessions,
confirmation, write tokens, geometry validation, side-panel export, and source
binding. The design must therefore be local to presentation and must not make a
new client authority for those rules.

## Goals / Non-Goals

**Goals:**

- Use the locked Taste image-to-code workflow as the only visual invention
  authority for `/` and `/app`.
- Establish one shared visual foundation with explicit semantic states,
  readable hierarchy, stable focus, and responsive transformations.
- Preserve current DOM/API hooks where they are behavior seams; change
  composition and styling around them rather than duplicating state.
- Make the confirm/write distinction and side-panel fallback more obvious.
- Keep the generated references, visual system, browser renders, and behavior
  contract traceable in repository documentation.

**Non-Goals:**

- No backend or provider architecture change.
- No framework migration or speculative component library.
- No new persistence, auth, storage, or PDF semantics.
- No runtime dependency on external reference-site assets.
- No deployment, production configuration, merge, or main-branch mutation.

## Decisions

### Keep existing behavioral seams

Presentation will wrap existing IDs, classes, state attributes, and event
listeners wherever possible. `app.js` remains the workflow coordinator;
`ui-state.js` remains the state-to-copy model; `worksheet-view.js` remains the
document renderer. This is preferred over splitting the 1,699-line coordinator
without a confirmed seam because the redesign is not evidence for a broader
architecture rewrite.

### Use a shared token layer with semantic state tokens

Landing and app styles will consume a single token source for canvas, ink,
muted text, focus, action, safe, caution, blocked, border, spacing, radius,
shadow, and type roles. State styling will use semantic names instead of
page-local colors so “confirmed/not written,” “written,” and “side panel” stay
consistent across both surfaces.

### Image-first reference ownership

Original Claros references will be generated after reconnaissance and analyzed
in `docs/redesign/VISUAL_SYSTEM.md`. They are the source of truth for
composition, density, typography, and state treatment. Taste v2 and
frontend-design remain inactive for visual invention in this experiment;
codebase-design is limited to seam decisions.

### Preserve content semantics while reorganizing grouping

The redesign can move task navigation, document preview, editor, voice status,
and confirmation grouping, but will retain labels, landmarks, live regions,
keyboard paths, and action IDs required by existing contract validation. Any
new decorative markup will be inert and will not be used to render parser or
model-controlled text as HTML.

### Verify in vertical slices

Implementation proceeds landing shell, landing proof/entry, workspace shell,
typed/review/write states, safety/export, and responsive treatment. Each slice
gets focused tests plus a browser render before the next slice. The backend is
exercised through the existing real endpoint path; missing local credentials are
reported rather than mocked.

## Risks / Trade-offs

- [Risk] A visual DOM reorganization can silently break event selectors or
  contract tests → [Mitigation] preserve required hooks, run frontend
  validation, inspect the full browser snapshot, and add regression coverage
  for any discovered defect.
- [Risk] More prominent state styling could accidentally imply that confirmation
  writes → [Mitigation] keep separate action labels and copy in the behavior
  contract, test confirmed-not-written and write states explicitly.
- [Risk] Parser-controlled text could become an XSS surface during markup work
  → [Mitigation] keep text insertion through existing safe paths and run the
  Vibe Security review on touched DOM and API boundaries.
- [Risk] Generated references can contain text/layout details that are not
  implementable or accessible → [Mitigation] treat references as visual
  direction, extract tokens in `VISUAL_SYSTEM.md`, and preserve semantic HTML,
  real controls, and responsive behavior in code.
- [Risk] Missing GCS/Gemini credentials limit end-to-end local verification
  → [Mitigation] run deterministic tests and no-credential failure paths,
  document the boundary, and do not claim live provider verification.

## Migration Plan

This is an experiment branch with no deployment. Apply changes in the isolated
worktree, run the documented gates, and leave the branch ready for human review.
Rollback is a branch/worktree decision; no production migration is required.

## Open Questions

None that affect the specification or task breakdown. Final visual details are
resolved by the generated references and rendered comparison loop.
