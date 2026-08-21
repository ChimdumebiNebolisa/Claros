## Context

See `proposal.md` for motivation and the capability specs for observable
requirements. Current `main` already filters the server-side product catalog to
`canonical-short-answer-ecosystems`, but `frontend/app.html` still hardcodes two
unsupported sample buttons. The contract evaluator consumes only the three
canonical fixtures and reports document-level decisions. The canonical contract
document now exists on `main`, but its content and inbound documentation links
still require validation against the implementation.

The production parser boundary, geometry authority, confirmation flow, provider
limits, privacy headers, container user, and deployment topology are frozen for
this pass. Evaluation labels remain AI-adjudicated silver.

## Goals / Non-Goals

**Goals:**

- Make every production sample entry point resolve only to the supported sample.
- Establish one concise contract document and make other current documentation
  link to it rather than restating divergent rules.
- Evaluate approximately 24 deterministic first-party PDFs spanning realistic
  supported variation and deliberate rejection cases.
- Produce actionable agreement metrics, reason-code counts, and per-fixture
  disagreement records with unsafe acceptance fixed at zero.
- Reproduce and repair only parser defects that violate the existing contract.
- Require the existing Python, frontend, and Docker pull-request checks on
  `main` when GitHub permissions permit a safe settings update.

**Non-Goals:**

- Broadening supported layouts, adding OCR acceptance, or changing workload
  ceilings.
- Replacing the parser, semantic provider, canonical model, write path, or
  deployment architecture.
- Treating synthetic-corpus agreement as human validation or universal quality.
- Adding a distributed quota, lifecycle, or benchmark platform.

## Decisions

### 1. Keep the server catalog authoritative and fix the static fallback

`sample_catalog.py` remains the production source of truth and continues to
filter canonical evaluation sources through its explicit supported-ID set. The
two unsupported buttons are removed from the static application markup, and
frontend/documentation tests assert that only the supported ID and label appear.
The runtime catalog fetch and default/deep-link alias behavior remain unchanged.

This is preferred to dynamically rebuilding the chooser because the current
static control is accessible before JavaScript and the defect is only stale
markup. Reworking sample rendering would add unrelated frontend state.

### 2. Represent the expanded corpus as deterministic source definitions

Add a fixture catalog under `evaluation/worksheet_contract_v1` containing
stable IDs, layout parameters, expected decisions, expected tasks, response
types, and expected rejection categories. A pure generator constructs PyMuPDF
documents from those definitions. Evaluation and tests generate PDFs into a
temporary or explicitly requested output directory instead of relying on
downloaded or private binary inputs.

The target inventory is approximately 24 fixtures, balanced across supported
and rejected cases. Supported definitions combine page count, prompt wrapping,
font size, margins, indentation, gap, line group, box, form-field, numeric, and
page-edge variations. Rejected definitions each emphasize one or more required
fail-closed structures, including OCR-only and transformed-page cases.

Source definitions are preferred to committing many opaque PDFs because they
make provenance, review, and deterministic regeneration explicit. Tests compare
fixture IDs and PDF hashes across repeated generation.

### 3. Use a closed-world fixture selector without granting geometry authority

The evaluator uses a deterministic fixture selector that may identify only
source blocks and response candidates extracted from each generated PDF. It may
declare response semantics or page roles needed to exercise a fixture, but it
cannot create text, IDs, regions, or coordinates. Every fixture still runs
through `parse_supported_worksheet`, so production geometry and whole-document
classification remain authoritative.

This isolates contract validation from live provider variability while testing
the same semantic/physical authority seam. A live provider benchmark would make
the corpus nondeterministic and is outside this pass.

### 4. Separate decision evidence from accepted-document geometry evidence

Every fixture contributes to decision agreement, supported acceptance,
unsupported rejection, unsafe acceptance, and rejection reason counts.
Question-count and question-order agreement are reported for fixtures whose
expectations define materialized questions. Response detection, association,
and response-type agreement are computed only from supported documents accepted
by the production seam; rejected documents never need to become writable merely
to expose internal geometry metrics.

The report schema is versioned, records eligible denominators, lists every
fixture result, and sorts IDs and reason-code maps before JSON serialization.
Generated reports omit timestamps, temporary paths, and environment-specific
values so a second run is byte-stable.

### 5. Triage every disagreement before changing parser behavior

Each disagreement is assigned one of four review dispositions: in-contract
parser defect, correct unsupported rejection, fixture expectation error, or
ambiguous and intentionally rejected. A parser modification is allowed only
after a minimal generated PDF reproduces a supported-contract violation and a
regression test captures it. Geometry or authorization checks are never loosened
solely to increase aggregate acceptance.

Red-team tests explicitly perturb decorative lines, choice numbering, aligned
line grouping, text/graphic overlap, adjacent-question association, staggered
columns, unclaimed regions, and semantic promotion attempts.

### 6. Keep one canonical contract document

`docs/SUPPORTED_WORKSHEET_CONTRACT.md` records the implemented boundary,
accepted response evidence, ordering/locality rules, workload ceilings,
classification outcomes, OCR limitation, deterministic authority, and
controlled 422 behavior. README, deployment, architecture, and current-product
documents link to it and retain only context-specific operational notes.
Historical provenance documents are annotated when necessary rather than
rewritten as if past stages had the current boundary.

### 7. Update branch protection through GitHub settings, not repository code

Inspect the current protection object for `main` and preserve existing review,
administrator, dismissal, and restriction settings. If authenticated
permissions allow, update only required status checks to strict mode with the
stable pull-request contexts `Python tests & lint`, `Frontend contract &
bundle`, and `Docker image build`. If the API denies the update, record the
exact manual repository setting and do not add a fake configuration file.

## Risks / Trade-offs

- **[Synthetic fixtures overfit extraction conventions]** → Combine layout
  parameters, keep source definitions reviewable, and report all individual
  outcomes rather than relying on one aggregate number.
- **[Fixture selector and expectations become circular]** → Keep supplied-ID
  selection separate from expected decisions, validate every selected ID
  exists, and let deterministic classification decide acceptance.
- **[Expanded evaluation slows CI]** → Keep the corpus near 24 small PDFs,
  avoid live providers/OCR engines, and measure the full suite before accepting
  the final inventory.
- **[Conservative rules reject legitimate-looking worksheets]** → Record every
  supported expectation disagreement individually; retain rejection unless the
  existing contract is clearly satisfied.
- **[Generated artifacts drift by platform]** → Use fixed PDF metadata, stable
  insertion order, rounded coordinates, sorted serialization, and repeated-run
  hash tests on Windows and CI.
- **[Branch-protection update overwrites unrelated policy]** → Read the existing
  configuration first and preserve all fields outside required status checks;
  stop and report when permissions or API shape are uncertain.

## Migration Plan

1. Record the current three-document report as the before baseline.
2. Correct sample markup and add catalog/UI/link regression tests.
3. Validate or update the canonical contract document and inbound links.
4. Add fixture definitions, deterministic generation, expanded report schema,
   and terminology/determinism policy tests.
5. Run the corpus, triage every disagreement, and make only proven in-contract
   fixes with regressions.
6. Run all release checks and confirm generated files leave no unintended diff.
7. Inspect and, if authorized, update `main` branch protection after stable CI
   check names have been observed.

Rollback is a normal revert of repository changes. Branch-protection rollback
restores the exact protection object captured before any settings update.
