# Stage 14 verification — Whole-product audit

## Scope

Exercise Claros as a student-pilot candidate after Stages 1–13. Fix P0/P1
findings that make the product confusing, fragile, inaccessible, unsafe, or
misleading. No major features; no canonical label/manifest edits.

## Audit evidence (offline)

| Check | Result |
|-------|--------|
| `python -m evaluation.canonical_v1.evaluate` | All association metrics 1.0; `false_positive_writable_regions: 0` |
| Sample vs upload path | Official samples use `POST /upload` (Stage 4 / product-flow tests) |
| Confirm ≠ write / deterministic stamp | Covered by write API + product-flow tests |
| Export requires written answer | Frontend + API 409; README corrected |
| Stage 13 deploy | `30419137249` success + smoke |

## Fixes shipped

| ID | Fix |
|----|-----|
| S14-P0-2 | Empty-task / semantic-rejected uploads set workspace `error` with clear copy (not `ready`) |
| S14-P1-1/2 | README export + layout-review claims match product behavior |
| S14-P1-3 | Replace worksheet best-effort `DELETE /api/assignments/{id}`; landing FAQ retention honesty |
| S14-P1-4 | Mobile expanded session: `aria-modal` + `documentViewport.inert` |
| S14-P0-1 | Optional `tests/test_stage14_live_canonical_semantics.py` for live Gemini when `CLAROS_LIVE_SEMANTICS=1` |

## Remaining honest gaps (accepted for revamp exit)

- Live Gemini semantics + Live voice are not exercised in default CI (require
  funded credentials / browser). Offline canonical harness + fail-closed empty
  task UX mitigate pilot confusion when semantics fail.
- Full NVDA / device keyboard matrix remains manual.
- OCR / scans / mixed packets remain out of supported boundary.

## Acceptance posture

Canonical structured-PDF product path meets the Stage 14 bar for the declared
boundary (three multi-task samples, deterministic confirm/write/export, typed
fallback, side panel, lifecycle delete on replace, docs aligned). Broader
worksheet claims stay deferred per roadmap §21.
