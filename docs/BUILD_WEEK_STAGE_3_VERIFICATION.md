# Revamp Stage 3 verification

## Scope and provenance

- Base SHA: `fa1b175` (`feat(document): establish canonical worksheet model`).
- Working branch: `codex/stage3-deterministic-extraction`, stacked locally on
  the Stage 2 checkpoint pending intentional review and remote publication.
- Scope: deterministic extraction and conservative canonical materialization
  for supported selectable-text worksheets. The change covers physical answer
  lines, bounded boxes, typed PDF fields, checkbox controls, explicit writable
  areas, source-backed choices, multi-region answer/show-work links, stable
  IDs, and side-panel fallbacks. It does not claim live Gemini, GCS, or
  production deployment verification.
- Contributor evidence: the current Codex task, repository diff, generated
  in-memory regression PDFs, and independent red-team findings. No unavailable
  session ID or exclusive authorship is claimed.

## Deterministic safety boundary

1. Physical IDs derive from page/type/geometry/source fingerprints rather than
   OCR insertion order or vector draw order.
2. Only vetted native `pdf_geometry` can auto-approve a current PDF-coordinate
   response target. Paddle OCR layout blocks remain non-writable evidence.
3. Explicit underscore glyph runs, typed empty text widgets, supported vector
   boxes, and vetted vector lines remain distinct response areas; they are not
   unioned into a task-level rectangle.
4. Checkbox controls create source-backed choice relations but cannot become
   text write targets. New uncertain checkbox regions cannot be approved by
   review, student projections suppress their write geometry, and export routes
   them to the side panel until a deterministic mark renderer exists.
5. Deterministic relationship validation rejects prompt-overlapping lines,
   reversed associations that skip another numbered prompt, cross-page
   selections, clipped geometry, dense grids, and other ambiguous selections.
   These preserve the task only as a side-panel fallback.
6. Normalized legacy records remain compatibility-only provenance; that
   exception does not authorize Paddle OCR evidence for current documents.
7. Native prompt evidence requires fully opaque, contrasted rendered glyphs
   and is rejected when it intersects a page graphic or image. Hidden,
   transparent, white, or graphic-covered source text cannot authorize a
   response target.
8. A persisted manifest with physical response links is authenticated with a
   domain-separated HMAC derived from the server-only session secret. The tag
   covers the canonical payload and storage assignment ID; missing, changed,
   or swapped tags fail closed. Old no-link records remain side-panel-only.
9. Export re-extracts actual source evidence and uses a fresh page-local
   Unicode-font alias, so canonical-record edits or a source font alias cannot
   redirect a write or substitute confirmed characters.

## Regression coverage

Generated-PDF regressions exercise:

- short-answer line plus separate show-work box;
- multiple-choice vector checkboxes and source-backed A/B/C labels;
- numeric underscore blanks using true glyph bounds while ignoring
  `snake_case`;
- empty, read-only, pre-filled text widgets, tiny checkbox widgets, and radio
  control typing, plus graphic/printed-content and choice-shaped field
  overlays;
- rectangle operators, four-line vector boxes, decorative dividers, table
  grids, and dense grid complexity limits;
- OCR configuration stability and OCR-only non-approval;
- transparent, white, graphic-covered, and artifact-overlaid source text;
- draw-order stability, reversed/cross-page selections, prompt-overlapping
  rules, and unknown semantic roles;
- review rejection of new checkbox promotion;
- source re-extraction during export, task/page approval gates, font-resource
  alias collisions, and side-panel-only legacy coordinate records;
- manifest HMAC determinism, tampering, assignment-ID replay, unsigned
  physical-target rejection, and post-review re-signing.

## Verified evidence

| Check | Result |
| --- | --- |
| Focused Stage 3 pipeline and contract regressions | Passed on independent review: `tests/test_document_pipeline.py`, `tests/test_canonical_document_contract.py`, `tests/test_canonical_v1.py` — 156 passed. |
| `python -m ruff check .` | Passed on independent review before the Stage 3 commit. |
| `npm run ci:frontend` | Passed on independent review (session-rules, ui-state, worksheet security/targets, validate:frontend, build:genai). Bundle rebuild artifact was discarded; not part of Stage 3. |
| Canonical Stage 3 acceptance (`python -m evaluation.canonical_v1.evaluate`) | **Met.** Metrics: task_count_accuracy `1.0`, task_count_exact_document_rate `1.0`, prompt_text_fidelity `1.0`, task_order_accuracy `1.0`, response_region_detection `1.0`, response_type_accuracy `1.0`, task_to_response_association_accuracy `1.0`, physical_response_detection `1.0`, physical_response_type_accuracy `1.0`, false_positive_tasks `0`, false_positive_writable_regions `0` (mean IoU `0.917697`). |
| Repeated-parse stability | Three consecutive evaluate runs and three `parse_document` ID snapshots were identical (`metrics_stable`, `ids_stable`). |
| Layout red-team regressions | In-repo: unnumbered wrap expansion, rounded-box edge demotion, parametric perturbations. Independent review added one controlled layout variation per canonical family (filled prompt cards + lines/boxes; enlarged checkboxes + explanation box; wrapped prompts + rounded show-work). Physical evidence recovered; no box-edge `answer_line` false positives; expected labels untouched. |
| Expected-label integrity | Preserved. `source.json` / `manifest.json` / expected labels / baseline provenance were not edited to improve scores. Stage 3 baseline rewritten only as evaluation evidence output. |
| Independent Stage 3 review | Completed after local acceptance. Diff review, focused suites, canonical evaluate, and controlled layout red-team found no valid P0/P1. Residual P2/P3 items and Docker gap are recorded below; none block Stage 3 acceptance. |

## Independent review

Independent Stage 3 review covered:

- the Stage 3 diff against the Stage 2 checkpoint;
- focused pipeline / contract / canonical_v1 suites;
- `python -m evaluation.canonical_v1.evaluate` acceptance metrics;
- one controlled layout variation per canonical family (filled prompt cards +
  lines/boxes; enlarged checkboxes + explanation box; wrapped prompts +
  rounded show-work);
- fail-closed write gates for ambiguous associations and checkbox text writes.

Outcome: no valid P0 or P1 findings. Stage 3 acceptance remains met. Residual
non-blocking findings are deferred to later roadmap stages rather than patched
into Stage 3 scope.

## Residual findings (deferred)

| ID | Severity | Finding | Why not Stage 3 | Intended later stage |
| --- | --- | --- | --- | --- |
| S3-P2-1 | P2 | Wrap-continuation expansion and intervening-text write-proof rules are duplicated / overlapping. Unnumbered multi-block prompts can still fail closed to the side panel even when physical regions are recovered. | Fail-closed is correct for Stage 3 extraction safety; tightening is product-flow polish, not a missed region gate. | Stage 4 (canonical sample product flow) and Stage 5 (confirmation / write integrity) |
| S3-P2-2 | P2 | `_drawing_is_closed_frame` treats `"re"` operators permissively. Writable minting is still gated by explicit labels, empty interior, contrast, and paper-like fill checks. | No false-positive writable regions on the canonical gate; narrowing the frame predicate is hardening, not acceptance repair. | Stage 5 (write/export integrity) or Stage 10 (test / parser rationalization) |
| S3-P2-3 | P2 | Offline `_CanonicalEvidenceSelector` selects among extracted blocks using expected prompt/geometry coverage. It is not a substitute for live Gemini semantic selection on production uploads. | Stage 3 acceptance intentionally measures deterministic physical IR plus offline evidence selection. Live sample UX is Stage 4. | Stage 4 (sample product flow) and Stage 9 (Gemini voice / semantic architecture) as applicable |
| S3-P3-1 | P3 | Unnumbered sentence-case word problems recover associations but do not meet numbered task-shape auto-approval, so regions stay `needs_review` / side-panel for auto-write. | Deterministic extraction and association are accepted; auto-write policy is intentionally conservative. | Stage 4 / Stage 5 |
| S3-P3-2 | P3 | Full-tree pytest coverage and frontend bundle CI were verified during recovery/review, but the Stage 3 gate itself is the canonical evaluate harness plus focused regressions. Broader suite rationalization remains open. | Not a Stage 3 product defect. | Stage 10 (test suite audit and rationalization) |
| S3-P3-3 | P3 | Local Docker Linux engine was unavailable, so `docker build -t claros:final .` image smoke was not run and is not claimed. | Environment limitation; not evidence of a successful or failed container build. | Stage 12 (observability, performance, and deployment) |

## Canonical fixture reconciliation

Fixtures required for Stage 3 acceptance live on this branch:

- `evaluation/canonical_v1/source.json` — authoritative semantic source
- `evaluation/canonical_v1/schema.py`, `generate.py`, `evaluate.py`
- `evaluation/canonical_v1/generated/manifest.json` — expected geometry/labels
- `evaluation/canonical_v1/generated/pdfs/*.pdf` — three first-party samples
- `evaluation/canonical_v1/generated/rendered/*.png` — visual previews
- `tests/test_canonical_v1.py` — regeneration/consistency harness

Decision recorded: belong on the Stage 3 branch (not a later merge-only detail).
They were copied from the fixture worktree rather than regenerated, preserving
byte-identical PDFs/manifest hashes. The evaluate harness targets Stage 3
`parse_document`; expected labels were not weakened.

## Root-cause matrix (structure causes, not fixture names)

| Structure cause | Symptom | Deterministic fix |
| --- | --- | --- |
| Selectable prompt text on filled / graphic-backed cards dropped as covered | 0 tasks | Treat paper-like fills and closed frames as chrome, not covering graphics |
| Rounded / path-encoded writable boxes missing (`l`/`c` cycles) | Missed box regions | Closed-frame geometry → bounded_box / writable_area |
| White-filled checkbox / box rejected as non-empty graphic | Missed controls | Paper-like fill exemption |
| Wrapped prompt continuation omitted from selected evidence | Association leap / side panel | Expand tight same-column wrap spans; allow unnumbered sentence-case anchors |
| Inset rounded-box edge minted as answer_line | Intervening FP blank blocked show-work | Overlap-aware rectangle-edge + writable-box ownership guards |
| Indented answer rule ignored left `Answer:` label | Line demoted to horizontal_rule_candidate | Nearby-label proximity includes left-of-stroke colon labels |
| Checkbox left of choice / prompt card | Choice association failed | Checkbox linker via same-row choice label |
| Explanation / show-work colon labels under-recognized | Multi-region roles incomplete | Explicit label cues for show-work / explanation |

## Recovery fixes applied during takeover

Interrupted Stage 3 left 15 focused pipeline failures. Root causes and fixes:

1. Vector `answer_line` minting required only narrow `Answer:`/`Show your work:` labels, so same-row colon fields and numbered answer blanks never surfaced. Restored Stage-2-style field/prompt evidence for minting, with Stage-3 guards: choice-list pages stay bare-rule, decorative heading underlines require a ≥20pt gap, and auto-approval remains separate.
2. Visibility contrast sampled display-rotated `page.rect` against unrotated extraction geometry, so rotated pages never proved visible strokes. Visibility pixmaps now render with rotation cleared and sampling uses the unrotated extraction frame.
3. Choice-list bare-rule regression looked only for `answer_line`; updated to accept `horizontal_rule_candidate` so forged approved regions still fail closed without physical response-area evidence.

## Deployment limitation

`docker build -t claros:final .` could not run because the local Docker Desktop
Linux-engine named pipe was unavailable. This is an environment limitation, not
evidence of a successful container build; container runtime verification
remains pending a running Docker daemon and is deferred to Stage 12. A Docker
Desktop named-pipe failure is not treated as successful container verification.
