# Revamp Stage 1 verification

## Scope and provenance

- Base SHA: `5c13307afe7488348ac1b25ffcd522de260333f3`.
- Working branch: `codex/stage1-runtime-safety`.
- Scope: runtime safety and provider consolidation only. No live Gemini or
  production-provider claim is made by this record.

## Verified evidence

| Check | Result |
| --- | --- |
| `python -m ruff check .` | Passed. |
| `python -m pytest tests/ --cov --cov-config=pyproject.toml --cov-report=term-missing` | Passed: 233 tests; 81.97% total coverage (72% required). |
| `npm run ci:frontend` | Passed: session rules, UI state, malicious worksheet-label DOM regression, frontend contract validation, and same-origin Gemini bundle build. |
| `npm audit --omit=dev --json` | No production dependency vulnerabilities reported. |
| `git diff --check` | Passed. |
| Local Playwright browser flow | Passed against a local demo configuration: landing, sample upload through normal `/upload`, typed answer review, explicit confirmation, unsafe-write disabled state, no browser console errors, and CSP/security headers on session start and confirmation responses. |
| Independent Stage 1 red team | No P0 remained after fixes. It verified literal `$x$` and U+03C0 export preservation, session-start allocation limiting, export snapshot reuse, and conflicting-environment failure. |

## Fixed red-team findings

1. PDF export no longer strips literal math delimiters or silently substitutes
   missing glyphs. It uses a bundled Unicode fallback and returns an explicit
   validation error for unsupported characters.
2. Durable session creation is capability-keyed and rate-limited before
   storage allocation; rate-limit telemetry now has fixed supported labels.
3. Export validates task snapshots and renders from the same loaded manifest
   snapshot, avoiding a second manifest read that could redirect a confirmed
   answer after a concurrent review change.
4. Conflicting nonempty `APP_ENV` and legacy `CLAROS_ENV` values fail at
   startup instead of selecting development mode silently.

## Deployment limitation

`docker build -t claros:final .` could not run because the local Docker
Desktop Linux-engine named pipe was unavailable. This is an environment
limitation, not evidence of a successful container build; container runtime
verification remains pending a running Docker daemon.
