## 1. Contract and production seam

- [x] 1.1 Add the supported worksheet specification and typed classification result.
- [x] 1.2 Add `parse_supported_worksheet` and route production assignment parsing through it.
- [x] 1.3 Return a controlled unsupported/ambiguous upload response and frontend message.

## 2. Deterministic support rules and budgets

- [x] 2.1 Enforce question/region type, local geometry, order, page, and ambiguity rules.
- [x] 2.2 Support one line, aligned line groups, and blank boxes; reject choices, tables, remote regions, and columns.
- [x] 2.3 Enforce page, question, semantic-call, timeout, and provider-attempt limits.

## 3. Audit defects

- [x] 3.1 Fix the stale landing test with stable behavior assertions.
- [x] 3.2 Delimit untrusted worksheet content in the tutoring prompt and add adversarial tests.
- [x] 3.3 Add private/no-store headers to capability/session worksheet responses.
- [x] 3.4 Make GitHub Actions the canonical bounded Cloud Run deployment and align docs/config.
- [x] 3.5 Migrate active evaluation output vocabulary to agreement/adjudication terms.
- [x] 3.6 Move build-only frontend packages, run the container as non-root, and normalize prerender output.

## 4. Evaluation and verification

- [x] 4.1 Add supported and deliberately unsupported deterministic fixture coverage.
- [x] 4.2 Run canonical narrow-product evaluation and demo/metrics checks.
- [x] 4.3 Run Python lint/tests, frontend validation/build, Docker build/smoke when available, and diff hygiene.
- [x] 4.4 Red-team unsupported layout acceptance and deterministic write authorization.
