# Claros Build Week Delta

## Provenance

- Baseline SHA: `d73969b571374458ac5febfb63551cbd1f6cb755`
- Working branch: `codex/mitch-bootstrap`
- Current work is intentionally uncommitted on the reconstruction branch.
- Contributors: Codex reconstruction work; no external contributor attribution
  is inferred.

## Evidence

- `npm run build` passes with the React/Vite production bundle.
- `npm test` passes the focused contract, placement, and state-machine suite.
- `npm run build-storybook` passes with the state stories and a11y addon.
- `npm run test:e2e` passes the landing-page axe smoke test after installing the
  local Playwright Chromium runtime.
- A browser smoke run against the local API and Vite dev server rendered the
  React PDF page and one current answer-region overlay.
- `npm audit --audit-level=high` reports zero vulnerabilities.
- The local server flow covers demo load, known-source upload, placement plan,
  explicit commit, and export. Unknown PDFs remain fail-closed.

## Scope boundary

The parser still accepts only the authored deterministic sample PDF. Durable
storage, physical TTL cleanup, live voice/provider verification, and a declared
first-party worksheet corpus remain deferred and are not claimed as complete.
