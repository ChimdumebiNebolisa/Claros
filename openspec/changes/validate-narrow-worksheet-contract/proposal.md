## Why

The narrowed worksheet contract is implemented, but the product still exposes
unsupported evaluation fixtures as official samples, its canonical contract
documentation is missing, and its three-document contract evaluation is too
small to demonstrate reliable fail-closed behavior. A focused validation pass
is needed before treating the current boundary as release-ready.

## What Changes

- Show only `canonical-short-answer-ecosystems` in the production sample UI
  while retaining multiple-choice and multi-region math fixtures for tests and
  evaluation.
- Add one canonical `docs/SUPPORTED_WORKSHEET_CONTRACT.md` and make product,
  architecture, and deployment documentation link to it consistently.
- Expand the deterministic first-party worksheet corpus to roughly 20–30
  realistic supported, ambiguous, and unsupported PDFs without broadening the
  product contract.
- Report agreement for document decisions, question counts and ordering,
  response-region detection, question-to-response association, response types,
  rejection reasons, and unsafe acceptance.
- Red-team false acceptance and false rejection, fixing only demonstrated
  defects for documents already inside the supported class.
- Verify the existing safety, cost, privacy, container, and deployment
  hardening and configure required `main` checks when repository permissions
  safely allow it.

## Capabilities

### New Capabilities

- `product-sample-catalog`: Production sample discovery and deep links expose
  only worksheets accepted by the current supported worksheet contract.
- `worksheet-contract-evaluation`: Deterministic first-party fixtures and
  agreement-based metrics demonstrate supported acceptance, unsupported
  rejection, and zero unsafe acceptance across realistic layout variation.

### Modified Capabilities

None. The sequential short-answer worksheet contract and write-authority
boundary remain unchanged.

## Impact

- Production sample catalog, frontend sample presentation, deep links, and
  their validation tests.
- Canonical contract, README, architecture, deployment, and Build Week
  documentation.
- `evaluation/worksheet_contract_v1`, its generated first-party fixtures and
  reports, plus contract and red-team tests.
- GitHub branch protection settings for `main`, if the authenticated repository
  permissions allow a safe update using existing CI check names.
- No parser redesign, generalized document support, write-authorization
  relaxation, provider expansion, or deployment architecture change.
