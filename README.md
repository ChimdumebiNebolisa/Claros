# Claros

Claros is a conversational worksheet workspace for students who need less
typing. A student uploads a PDF, talks naturally with one agent, reviews the
exact proposed answer, explicitly approves it, and downloads a derivative PDF
built only from approved answers.

## Local run

Install Node 22, Python 3.12 with the repository virtual environment, Java 21,
and Maven 3.9.11. Copy `.env.example` to `.env`, set the server-only
`CLAROS_OPENAI_API_KEY`, install dependencies with `npm ci`, then start the
real application with one command:

```powershell
npm start
```

Open `http://127.0.0.1:8080/app`. This command builds the V2 frontend and
OpenPDF worker, obtains the pinned qpdf binary on Windows when needed, and
starts the FastAPI application on port 8080. It forces the real OpenAI semantic
and Realtime adapters plus OpenPDF; a missing key, provider failure, Java/qpdf
failure, or invalid PDF is surfaced as an error and never replaced by fixture
behavior. The sample button submits the checked-in PDF through the same
assignment endpoint used by file upload.

The visual-state and browser checks are available with `npm run build-storybook`
and `npm run test:e2e`. The latter builds the app, serves the production bundle,
and runs the Playwright/axe smoke test.

Fixture scenarios remain available only to tests and Storybook through their
explicit fixture URLs. They are not the normal `/app` runtime.

## Product contract

The supplied reconstruction PRD is the product source of truth and the supplied
`CLAROS_DESIGN.md` is the visual source of truth. The active OpenSpec change is
`openspec/changes/claros-reconstruction/`.

The first slice deliberately excludes scans/OCR, multiple choice, tables,
drawings, teacher review, arbitrary geometry, and production persistence. These
are new contracts, not hidden fallbacks.

## Safety notes

- Session identifiers are HttpOnly cookies; no assignment secrets are stored in
  browser storage.
- Placement and commit are server-owned and bound to exact answer text.
- The original PDF is never mutated; export returns a derivative PDF.
- Voice is optional. If microphone capture is unavailable, typed input remains
  complete in the same conversation.

## OpenPDF V2 export path

The local command selects OpenPDF explicitly; there is no automatic fallback.
OpenPDF verifies Java 21+, its shaded worker JAR, the allowlisted Noto Sans
font, and qpdf at startup. Each derivative stays quarantined until qpdf and the
independent PDFBox validator pass. PDF.js remains a CI/release compatibility
check rather than part of the synchronous export request.
