# Deploy Claros to Google Cloud Run

The only supported production deployment path is
`.github/workflows/deploy.yml`. It runs verification, builds an immutable image,
deploys it to Cloud Run, and probes `/health`, `/`, and `/app` after deployment.

## Runtime contract

The workflow deploys with:

- `APP_ENV=production`, GCS storage, and Gemini document semantics;
- an explicit runtime service account;
- `SESSION_HMAC_SECRET` and `GEMINI_API_KEY` injected from Google Secret Manager;
- an 8-page, 40-question, 8-provider-call worksheet budget;
- one request per container, zero minimum instances, and two maximum instances;
- a five-minute request timeout plus startup and liveness probes on `/health`.

Production startup fails when its GCS bucket, Google Cloud project, Gemini API
key, or session HMAC secret is missing. The service accepts only sequential
short-answer PDFs described in `docs/SUPPORTED_WORKSHEET_CONTRACT.md`.

## Operator procedure

Configure the GitHub and Google Cloud prerequisites in
`docs/github-actions-deploy.md`, then run the **Deploy to Cloud Run** workflow.
`deploy.sh` intentionally does not duplicate the workflow's deployment flags.

## Routes

- `/health` is the dependency-free Cloud Run probe.
- `/` is the marketing page.
- `/app` is the worksheet application.
- Capability, session, write, assignment, and export responses use
  `Cache-Control: private, no-store`.
