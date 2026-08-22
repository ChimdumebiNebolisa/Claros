## Context

The branch was intentionally cleared after the current `main` baseline was
preserved. The supplied reconstruction PRD is the product authority and the
supplied `CLAROS_DESIGN.md` is the visual authority. The first rebuilt slice is
deliberately narrow: a deterministic first-party sample worksheet is fully
supported; other PDFs fail closed until a parser can produce physical evidence.

## Goals / Non-Goals

**Goals:**

- Keep one small domain model for supported worksheets, questions, answer
  regions, placement plans, and committed answers.
- Connect upload/demo, draft, review, commit, resume cookie, and export behavior
  end to end with explicit failure states.
- Make the source preview visually primary and preserve the supplied light-first
  institutional design system across public and product surfaces.
- Keep server-owned authorization and placement semantics behind a real HTTP
  seam, with deterministic in-memory adapters suitable for local verification.

**Non-Goals:**

- OCR, choice questions, tables, drawings, teacher review, arbitrary geometry,
  or broad worksheet compatibility in this reconstruction slice.
- Production storage, live Gemini credentials, or deployment changes.
- A second design-system source of truth or Impeccable project lifecycle files.

## Decisions

### Deep modules and seams

- `src/domain/contracts.ts` is the typed contract module. Zod schemas validate
  values crossing the API seam and the domain types keep state projections
  explicit.
- `src/domain/placement.ts` owns placement classification and copy. It has a
  small interface (`classifyPlacement`, `placementLabel`) and is tested without
  rendering or transport.
- `src/domain/workspace-machine.ts` owns the observable product state graph.
  React dispatches events; it does not decide whether a plan token is valid.
- `src/adapters/api.ts` is the browser HTTP adapter. The server owns assignment,
  plan, commit, session, and export behavior behind `/api/v1`.
- `server/fixture.mjs` is a deterministic source adapter for the authored sample
  PDF. The upload route hashes extracted PDF bytes and accepts only that known
  source; unknown PDFs reject with a stable code instead of inventing evidence.

### Stack

React 19, TypeScript, Vite 8, React Router, Tailwind v4, Radix/shadcn source
primitives, XState v5, Zod 4, React Dropzone, React PDF, Resizable Panels,
Lucide, Inter, Vitest, Testing Library, Storybook with its a11y addon, MSW,
Playwright with axe, and a built-in Node HTTP server are used because each maps
to a specific PRD requirement. React PDF renders the immutable source page and
Claros owns the coordinate overlays; no prebuilt PDF toolbar competes with the
design reference.

### Visual routing

`frontend-design` supplies the project-wide baseline. The `/app` upload and
workspace surfaces are **Impeccable-primary** in bounded Operate mode because
task completion, state complexity, keyboard behavior, and accessibility dominate.
The `/` marketing surface is **frontend-design-primary** because the supplied
reference already settles its composition and restrained public-facing language.
`CLAROS_DESIGN.md` outranks generic specialist defaults for palette, typography,
spacing, border radius, copy, and state semantics.

### Security and privacy

- Session identifiers are random, HttpOnly, SameSite cookies; no assignment
  secrets are stored in browser storage.
- The server validates ownership, plan expiry, assignment/question association,
  exact answer text, and placement before commit.
- Uploaded bytes are treated as untrusted. Unknown files fail closed; text is
  rendered as text; provider credentials are server-only and not part of this
  local slice.
- Export rejects incomplete assignments and renderer-unsafe glyphs rather than
  silently normalizing or rerouting.

## Risks / Trade-offs

- [Parser coverage] → Only the authored sample PDF is accepted in this first
  slice; expand through a new worksheet-contract spec and evidence corpus.
- [In-memory retention] → The local API is intentionally process-local; add a
  durable store and physical TTL cleanup before production claims.
- [PDF preview fidelity] → The local fixture renders through React PDF and
  overlays supplied answer-region coordinates; broader page geometry remains
  deferred until evidence-backed parsing exists.
- [Voice provider] → Browser SpeechRecognition is optional and no provider
  credentials are bundled; live Gemini integration remains an explicitly
  unverified boundary.

## Migration Plan

1. Run `npm install`, `npm run build`, and `npm test`.
2. Start `node server/index.mjs` and `npm run dev` for the local vertical slice.
3. Use `/api/v1/demo.pdf` as the deterministic fixture for upload and export
   checks.
4. Add parser adapters only after new evidence and acceptance tests exist.

## Open Questions

None for this slice. Production storage, external corpus expansion, and live
voice provider verification are intentionally deferred scope, not unresolved
decisions.
