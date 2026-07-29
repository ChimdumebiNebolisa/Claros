# Stage 13 verification — Documentation and repository convergence

## Scope

Converge active documentation on the current Claros product (Stages 1–12 on
`main`) so a new engineer can understand present-tense behavior without
reconstructing contest-era OpenAI plans or July PDF-investigation defaults.

## Invariants preserved

- Confirm ≠ write; deterministic write ownership unchanged (docs only).
- No changes to canonical eval labels, manifests, or silver freeze artifacts.
- Deploy workflow (`.github/workflows/deploy.yml`) not modified.

## Changes (summary)

| Area | Action |
|------|--------|
| `README.md` | Present-tense banner; typed+voice flow; confirm≠write; hybrid parser default; ARCHITECTURE as canonical pointer |
| `PRODUCT.md` | Human-free boundary; mic optional |
| `docs/github-actions-deploy.md` | `/health` (not `/healthz`); `APP_ENV` + `SESSION_HMAC_SECRET` Secret Manager |
| Build Week / PDF investigation / audit journals | Historical banners; demote “current execution order” / OpenAI live claims |
| `docs/CLAROS_REVAMP_ROADMAP.md` | Status through Stage 12; silver-language instead of “ground truth” |
| `docs/BUILD_WEEK_DELTA.md` | Stage 12 deploy evidence + Stage 13 record |

## Red team (new-engineer read)

| Question | Result |
|----------|--------|
| What is the current AI provider? | Gemini (README / ARCHITECTURE); OpenAI docs labeled historical |
| Confirm vs write? | README Core Product Rule: confirm ≠ write; no conversation-as-write-authority |
| Health probe? | `/health` in DEPLOY.md and github-actions-deploy.md |
| Parser default? | `PDF_PARSER_MODE=hybrid` in README env table; July legacy-default docs historical |
| Teacher review required? | No — AGENTS / PRODUCT / historical banners |

## Acceptance

The repository has one coherent present tense for product docs, with historical
evidence clearly labeled.

## Remaining (Stage 14)

Whole-product audit of runtime paths; no major features.
