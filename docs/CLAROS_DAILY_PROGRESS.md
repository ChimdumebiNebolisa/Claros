# Claros Daily Progress

Last updated: 2026-07-11 (America/Chicago)

## Current state

- Current roadmap phase: Phase 1 — Audit and baseline
- Current work unit: None; next is inventory legacy frontend files and references
- Active entrypoints under verification: `frontend/landing.html` at `/`; `frontend/app.html` at `/app`
- Legacy files still present: `frontend/index.html`; `frontend/index.backup.html`

## Ordered work-unit checklist

### Phase 1 — Audit and baseline

- [x] Inventory active frontend entrypoints
- [ ] Inventory legacy frontend files and references
- [ ] Run and record current Python tests
- [ ] Run and record coverage
- [ ] Run and record frontend checks
- [ ] Run and record frontend bundle build
- [ ] Run and record Docker build
- [ ] Run and record smoke tests
- [ ] Capture active landing and application states across required viewports and accessibility modes
- [ ] Audit active hard-coded colors against tokens
- [ ] Trace the complete product workflow
- [ ] Map storage and lifecycle behavior
- [ ] Create producer-to-consumer blast-radius map
- [ ] Inventory user-facing privacy, accessibility, and retention claims

### Later phases

- [ ] Phase 2 — Landing-page visual foundation
- [ ] Phase 3 — Landing-page structure
- [ ] Phase 4 — Application hierarchy redesign
- [ ] Phase 5 — Frontend modularization
- [ ] Phase 6 — Browser and accessibility testing
- [ ] Phase 7 — Session-secret hardening
- [ ] Phase 8 — Write-token and storage concurrency
- [ ] Phase 9 — Assignment and session expiration
- [ ] Phase 10 — Logging and privacy hardening
- [ ] Phase 11 — PDF processing hardening
- [ ] Phase 12 — Deployment hardening
- [ ] Phase 13 — Privacy-safe observability
- [ ] Phase 14 — Legacy cleanup
- [ ] Phase 15 — Documentation reconciliation

## Work-unit evidence

### Inventory active frontend entrypoints

Blast radius before editing: documentation, a stale comment in the shared session-rule asset, and static-route regression tests only. No route, UI, API, storage, PDF, session, write-token, or deployment behavior will change.

Producer-to-consumer trace:

- FastAPI `GET /` in `main.py` resolves `config.ROOT/frontend/landing.html`; that document loads `/styles/tokens.css` and `/styles/landing.css` and links to `/app`.
- FastAPI `GET /app` in `main.py` resolves `config.ROOT/frontend/app.html`; that document loads `/styles/tokens.css`, `/styles/app.css`, `/session-rules.js`, and `/app.js`.
- Dedicated FastAPI routes serve the active JavaScript, CSS, logo, favicon, and bundled Gemini SDK assets.
- `Dockerfile` copies the entire `frontend` directory. CI validates the active HTML contracts; deployment smoke checks probe `/`, `/app`, and `/styles/tokens.css`.
- `frontend/index.html` and `frontend/index.backup.html` contain legacy markers and have no FastAPI page routes. Packaging them is not evidence that they are served.

## Completed work units

- 2026-07-11 — Inventory active frontend entrypoints. Confirmed the FastAPI producer routes, exact HTML consumers, asset chain, Docker packaging, CI validation, and deployment probes; added route-to-file and legacy-route regression coverage; corrected the stale `index.html` source comment.

## Deferred items and blockers

- All later roadmap units are deferred in roadmap order.
- No blocker for the current work unit.

## Commands and verification

- `git status --short` — exit 0; unrelated untracked `.cursor/`, `.impeccable/`, `.playwright-cli/`, `DESIGN.md`, `PRODUCT.md`, and screenshot observed and preserved.
- `python scripts/validate_frontend.py` — exit 0; 5 validators passed.
- `python -m pytest tests/test_static_assets.py tests/test_frontend_contract.py -q` — exit 0; 7 passed in 11.03s.
- First combined post-change verification attempt — exit 124 after the 120-second command timeout; no test failure was reported. An isolated rerun completed successfully, so this was treated as a local process-duration issue rather than a product failure.
- `python -m pytest tests/test_static_assets.py -vv -s` — exit 0; 7 passed in 20.60s.
- `python -m ruff check tests/test_static_assets.py` — exit 0; all checks passed.
- `python scripts/validate_frontend.py` (post-change) — exit 0; 5 validators passed.
- `python -m pytest tests/test_static_assets.py tests/test_frontend_contract.py -q` (post-change) — exit 0; 9 passed in 14.17s.
- `git diff --check` — exit 0; only Git line-ending notices for two existing tracked text-file conventions.

## Review records

- Accessibility findings: inventory-only unit; no rendered behavior changed. Active pages share focus and reduced-motion tokens, but full keyboard, zoom, responsive, screen-reader, microphone-denial, and failure-state verification remains pending.
- Security and privacy decisions: no authorization, token, storage, logging, provider, or data-lifecycle behavior changed; no new public claim added.
- Architectural decisions: FastAPI remains the page and asset server; active vanilla HTML entrypoints remain separate landing and worksheet documents.
- Files and systems affected: progress documentation, static route tests, and one frontend source comment only.
- Screens or states verified: static response identity for `/` and `/app`; visual states not yet verified.
- Production behaviors not verified locally: Cloud Run routing, deployed asset contents, credentials, live GCS, Gemini Live, and post-deploy smoke checks.
- Public claims verified against code: only the active and legacy entrypoint statements above. Broader README claims remain unaudited.
