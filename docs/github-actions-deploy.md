# GitHub Actions deployment for Claros

`.github/workflows/deploy.yml` is the single production deployment definition.
It runs on pushes to `main` and by manual dispatch. Do not maintain a second set
of Cloud Run flags in a local script or document.

## GitHub configuration

The deploy job uses Workload Identity Federation and needs these repository
secrets:

| Secret | Purpose |
|---|---|
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `GCP_WIF_PROVIDER` | Full Workload Identity provider resource name |
| `GCP_SERVICE_ACCOUNT` | Service account impersonated by GitHub Actions |
| `GCP_RUNTIME_SERVICE_ACCOUNT` | Least-privilege identity used by Cloud Run |
| `GCS_BUCKET_NAME` | Assignment object bucket name, without `gs://` |

No long-lived Google service-account JSON key or Gemini key belongs in GitHub
Secrets. GitHub receives short-lived credentials through OIDC/WIF.

## Google Cloud configuration

Create these Secret Manager secrets before deploying:

- `claros-session-hmac`: a strong random session-signing secret;
- `claros-gemini-api-key`: the Gemini API credential.

Grant the runtime service account `roles/secretmanager.secretAccessor` on both
secrets and object read/write access scoped to the assignment bucket. Grant the
GitHub deploy identity only the roles needed to submit Cloud Builds, deploy Cloud
Run revisions, and act as the configured runtime service account.

## Deployed settings

The workflow explicitly sets production mode, GCS storage, Gemini document
semantics, workload ceilings, bounded Cloud Run scaling, request concurrency,
and request timeout. It configures startup and liveness HTTP probes at `/health`
and keeps Cloud Run's deploy-time health check enabled. Secret values are bound
from Secret Manager rather than embedded in command-line environment values.

The current supported upload shape is documented in
[`SUPPORTED_WORKSHEET_CONTRACT.md`](SUPPORTED_WORKSHEET_CONTRACT.md).
Unsupported PDFs return a controlled 422 response and do not create a writable
assignment.

## Deploy and verify

Run the **Deploy to Cloud Run** workflow from GitHub Actions or merge to `main`.
The workflow blocks deployment unless Python lint/tests, frontend checks, and a
production Docker build pass. After deployment it probes:

- `/health`
- `/`
- `/app`
- `/styles/tokens.css`

For a functional production check, upload a supported short-answer worksheet,
confirm an answer, and verify the exported PDF writes the exact confirmed text
inside the deterministic answer region.

As of 2026-08-21, `main` branch protection requires strict, up-to-date
`Python tests & lint`, `Frontend contract & bundle`, and `Docker image build`
contexts. This is a GitHub repository setting, not a checked-in deployment
substitute.

## Failure diagnosis

| Symptom | Check |
|---|---|
| WIF authentication fails | Provider resource, repository attribute binding, and deploy service account |
| Revision does not start | Required production configuration and Secret Manager access |
| Upload fails after startup | Runtime service-account access to the GCS bucket and Gemini secret |
| Unsupported upload returns 422 | Compare the PDF with the supported worksheet contract; do not bypass classification |
| Health probe fails | Container logs and dependency-free `/health` response |

The public Cloud Run service is intentional; capability tokens and server-side
authorization protect session/write operations. Public access does not relax
the deterministic write contract.
