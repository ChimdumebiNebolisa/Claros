## 1. Baseline and Product Surface

- [x] 1.1 Record the current three-document evaluator result and production sample inventory as the before baseline, and verify the baseline records one supported fixture, two rejected fixtures, and zero unsafe acceptances
- [x] 1.2 Remove unsupported official-sample controls and stale production descriptions, then verify catalog, static markup, default, and deep-link tests expose only `canonical-short-answer-ecosystems`

## 2. Canonical Contract Documentation

- [x] 2.1 Validate `docs/SUPPORTED_WORKSHEET_CONTRACT.md` against the parser, workload, classification, and authority implementation, then verify its required boundary sections are present
- [x] 2.2 Link current README, architecture, deployment, product, and verification documentation to the canonical contract and annotate superseded historical sample claims, then verify a documentation consistency test passes

## 3. Deterministic Evaluation Corpus

- [x] 3.1 Add a reviewable fixture-definition schema and pure PyMuPDF generator for approximately 24 first-party PDFs, then verify repeated generation has identical sorted IDs and SHA-256 hashes
- [x] 3.2 Add supported fixtures covering the specified prompt, response-region, typography, spacing, pagination, page-edge, count, and response-type variations, then verify corpus inventory tests cover every required supported dimension
- [x] 3.3 Add rejected fixtures covering choice, table, keyed/guide, essay, remote, multi-column, ambiguous/unclaimed, cross-page, transformed, scan, questionless, and unmappable layouts, then verify corpus inventory tests cover every required rejection dimension
- [x] 3.4 Implement a closed-world deterministic fixture selector that can select only extracted source and response IDs, then verify fabricated or unauthorized IDs fail closed

## 4. Evaluation and Red-Team Triage

- [x] 4.1 Expand the evaluator and stable report schema with all requested decision, acceptance/rejection, unsafe-acceptance, question, region, association, response-type, and rejection-reason metrics, then verify report schema and approved terminology tests pass
- [x] 4.2 Run all fixtures through the production parser seam, record an individual review disposition for every disagreement, and verify supported failures are explained and unsafe acceptances equal zero
- [x] 4.3 Add red-team cases for decorative lines, choice numbering, line grouping, overlap, adjacent association, staggered columns, unclaimed regions, and unauthorized semantic promotion; fix only reproduced in-contract defects and verify each fix with a focused regression test

## 5. Hardening, Repository Policy, and Release Verification

- [x] 5.1 Re-run hardening coverage for geometry authority, confirmation/write tokens, provider limits, privacy headers, non-root container execution, and single-instance deployment assumptions, then verify no safeguard regresses
- [x] 5.2 Inspect `main` branch protection and, if authorized, require strict `Python tests & lint`, `Frontend contract & bundle`, and `Docker image build` checks while preserving other settings; otherwise record the exact manual GitHub setting
- [ ] 5.3 Update architecture, verification, and Build Week evidence with the final corpus/result provenance and run ruff, full pytest with coverage, frontend CI, canonical and expanded evaluations, demo validation, Docker build, and `git diff --check`; verify generated outputs are stable and the worktree contains no unintended files
