# Claros working agreement

## Mission and supported boundary

Claros is a human-free worksheet-understanding and tutoring system. It
supports structured PDF worksheets with deterministic physical evidence. For
uncertain layouts, Claros routes answers to a safe side panel rather than
guessing a location. It does not require teacher, administrator, or annotator
review during normal use.

## Non-negotiable safety boundaries

- Never invent source text, source-block IDs, response-candidate IDs, or PDF
  coordinates.
- Models may select from supplied physical evidence and propose tutoring
  actions; deterministic code owns geometry, validation, student confirmation,
  write-token issuance, authorization, overflow handling, and PDF changes.
- Never write an answer until the student explicitly confirms the exact
  proposed answer.
- Keep a typed, accessible fallback. Microphone access must never be required.
- Preserve original worksheet pages. Use the side panel when a physical region
  is missing, uncertain, invalid, or cannot fit a confirmed answer.

## Privacy, secrets, and documents

- Do not read, print, commit, or log secret values. `.env` files and browser
  profiles are local-only.
- Do not commit external PDFs, private worksheets, raw provider payloads, or
  generated corpus output without explicit rights and privacy confirmation.
- Avoid content logging. Record hashes, sizes, latency, cost, and reason codes
  instead.
- Document logical versus physical retention honestly; do not claim automatic
  deletion without verified lifecycle configuration.

## Evaluation language

All document labels are AI-adjudicated silver. Never call them human gold,
ground truth, expert labels, human-verified, accuracy, or correctness.
Metrics must use agreement, adjudication, abstention, validator-catch, and
unsafe-placement language. Any F1 must be labelled "silver-relative agreement
/ provisional F1 against AI-adjudicated silver".

## Change and test expectations

- Make the smallest focused change; preserve unrelated local work.
- Add a regression test for each confirmed defect.
- Update architecture, Build Week delta, and verification documentation when a
  product boundary, provider, storage policy, evaluation method, or deployment
  requirement changes.
- Run the narrowest relevant tests first. Before a release, run:

  ```powershell
  python -m ruff check .
  python -m pytest tests/ --cov --cov-config=pyproject.toml --cov-report=term-missing
  npm run ci:frontend
  docker build -t claros:final .
  git diff --check
  ```

- Run benchmark validation/freezing, compiler evaluation, browser, PDF,
  security, and provider-mock suites whenever their related code changes.
- Do not claim provider or production verification without the corresponding
  live evidence.

## Build Week provenance and commits

- Record the baseline SHA, current SHA, contributors/co-authors, and evidence
  for each Build Week claim. Do not fabricate a Codex session ID or attribute
  all contest-period work to Codex.
- Keep commit staging intentional. Never include secrets, private documents,
  `output/`, local corpus data, or browser state.
- Keep this file and `docs/BUILD_WEEK_DELTA.md` current as the implementation
  changes.

## Engineering

Before non-trivial code, architecture, schema, integration, or refactoring work,
read [`docs/agents/engineering.md`](docs/agents/engineering.md).

- Preserve the behavior contract in `docs/redesign/BEHAVIOR_CONTRACT.md` before changing presentation.
- Use the active OpenSpec change for substantive requirement, architecture, and task changes.
- Keep typed operation, explicit answer confirmation, safe placement, and side-panel fallback intact.
- Route visual invention for this experiment through the locked `image-to-code` authority; keep other visual skills inactive unless a bounded diagnostic is explicitly justified.
