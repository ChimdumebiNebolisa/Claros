# GitHub Actions deploy setup for Claros

This document describes how Claros deploys to Google Cloud Run from GitHub Actions, which secrets to configure, and how to verify production after a successful deploy.

## What the deploy workflow does

Workflow file: `.github/workflows/deploy.yml`

Trigger: push to the `main` branch.

Steps:

1. Check out the repository.
2. Install Node 20 and build `frontend/genai.bundle.js` (`npm install`, `npm run build:genai`).
3. Authenticate to Google Cloud using Workload Identity Federation (WIF).
4. Configure `gcloud` with the project from `GCP_PROJECT_ID`.
5. Build and push a container image with Cloud Build:
   - Image: `gcr.io/${GCP_PROJECT_ID}/claros`
6. Deploy to Cloud Run:
   - Service name: `claros`
   - Region: `us-central1`
   - Public access: `--allow-unauthenticated`
   - Runtime env vars: `GEMINI_API_KEY`, `GCS_BUCKET_NAME`, `GOOGLE_CLOUD_PROJECT`

The workflow does **not** change application code. It builds the Docker image from the `Dockerfile`, which copies `main.py`, `parser.py`, `agent.py`, `exporter.py`, the full `frontend/` directory, and `test_assignment.pdf`.

## Authentication model

The workflow uses **Workload Identity Federation only**.

```yaml
uses: google-github-actions/auth@v2
with:
  workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
  service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}
```

- It does **not** use `credentials_json`.
- It does **not** use a service account JSON key stored in GitHub Secrets.
- The job requires `permissions: id-token: write` so GitHub can issue an OIDC token for WIF.

If `GCP_WIF_PROVIDER` or `GCP_SERVICE_ACCOUNT` is missing or empty, the "Authenticate to Google Cloud" step fails.

## Required GitHub repository secrets

Add these at: **GitHub repository → Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Purpose |
|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud project ID for deploy and runtime |
| `GCP_WIF_PROVIDER` | Full WIF provider resource name for GitHub OIDC |
| `GCP_SERVICE_ACCOUNT` | Deploy service account email (impersonated by Actions) |
| `GEMINI_API_KEY` | Gemini API key for Cloud Run runtime |
| `GCS_BUCKET_NAME` | GCS bucket name for uploaded assignment PDFs |

## Value format for each secret

### `GCP_PROJECT_ID`

- **Format:** Project ID string, for example `my-claros-project`.
- **Not** the numeric project number.
- The production URL uses project number `505797934944`, but this secret must be the **project ID**.

Find the project ID:

```bash
gcloud projects describe 505797934944 --format="value(projectId)"
```

### `GCP_WIF_PROVIDER`

- **Format:** Full resource name:

```text
projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
```

Example:

```text
projects/505797934944/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

### `GCP_SERVICE_ACCOUNT`

- **Format:** Service account email:

```text
SERVICE_ACCOUNT_NAME@PROJECT_ID.iam.gserviceaccount.com
```

Example:

```text
claros-github-deploy@my-claros-project.iam.gserviceaccount.com
```

### `GEMINI_API_KEY`

- **Format:** Gemini API key string from Google AI Studio or your GCP setup.
- Injected into Cloud Run as `GEMINI_API_KEY` at deploy time.

### `GCS_BUCKET_NAME`

- **Format:** Bucket name only, for example `claros-assignments`.
- Do not include the `gs://` prefix.
- Injected into Cloud Run as `GCS_BUCKET_NAME` at deploy time.

## Which values are sensitive

| Secret | Sensitive? | Notes |
|--------|------------|-------|
| `GCP_PROJECT_ID` | No | Public identifier |
| `GCP_WIF_PROVIDER` | No | Resource name, not a credential |
| `GCP_SERVICE_ACCOUNT` | No | Email address |
| `GEMINI_API_KEY` | **Yes** | API credential |
| `GCS_BUCKET_NAME` | Low | Bucket name is usually not secret, but treat repo secrets as private |

Deployment auth uses short-lived OIDC tokens via WIF, not a long-lived JSON key in GitHub.

## Google Cloud WIF setup requirements

You need these Google Cloud resources:

1. **Workload Identity Pool** (global)
2. **Workload Identity Provider** (OIDC, issuer `https://token.actions.githubusercontent.com`)
3. **Deploy service account** (used only for CI deploy)
4. **IAM binding** allowing the GitHub repository to impersonate that service account

Recommended attribute restriction:

- Repository: `ChimdumebiNebolisa/Claros`
- Branch (optional, tighter): `refs/heads/main`

Example setup commands (edit variables before running):

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export PROJECT_NUMBER="505797934944"
export POOL_ID="github-pool"
export PROVIDER_ID="github-provider"
export DEPLOY_SA_NAME="claros-github-deploy"
export GITHUB_OWNER="ChimdumebiNebolisa"
export GITHUB_REPO="Claros"

gcloud config set project "$PROJECT_ID"

gcloud services enable iamcredentials.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  storage.googleapis.com

gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions pool"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --issuer-uri="https://token.actions.githubusercontent.com"

gcloud iam service-accounts create "$DEPLOY_SA_NAME" \
  --display-name="Claros GitHub deploy"

export DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"
```

Skip create steps if pool, provider, or service account already exist.

## Required IAM roles

### Deploy service account (GitHub Actions)

Grant these on the deploy service account (project-level bindings shown):

| Role | Why |
|------|-----|
| `roles/iam.workloadIdentityUser` | On the SA: allows GitHub OIDC to impersonate it |
| `roles/cloudbuild.builds.editor` | Run `gcloud builds submit` |
| `roles/run.admin` | Deploy to Cloud Run |
| `roles/storage.admin` | Push to `gcr.io` (Container Registry) |
| `roles/iam.serviceAccountUser` | Act as runtime service account during deploy if needed |

Example:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

## Runtime Cloud Run and GCS requirements

The workflow sets these **runtime** environment variables on the Cloud Run service:

| Env var | Source |
|---------|--------|
| `GEMINI_API_KEY` | GitHub secret `GEMINI_API_KEY` |
| `GCS_BUCKET_NAME` | GitHub secret `GCS_BUCKET_NAME` |
| `GOOGLE_CLOUD_PROJECT` | GitHub secret `GCP_PROJECT_ID` |

The workflow does not set `GEMINI_TEXT_MODEL` (the app defaults to `gemini-2.5-flash`).

### GCS bucket

- Create a bucket in the same project (or ensure cross-project access is configured).
- The Cloud Run **runtime** service account must read and write objects under `assignments/{assignment_id}/`.

If the workflow does not pass `--service-account` to `gcloud run deploy`, Cloud Run uses the project default Compute Engine service account unless a previous deploy changed it.

Grant storage access to the runtime service account:

```bash
export RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
export GCS_BUCKET="your-gcs-bucket-name"

gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/storage.objectAdmin"
```

Without this, deploy may succeed but `/upload` and session endpoints will fail at runtime.

## How to rerun deployment after secrets are added

1. Add all five repository secrets listed above.
2. Confirm values (especially `GCP_PROJECT_ID` is the project ID, not `505797934944`).
3. Rerun deployment using one of:
   - **Re-run failed jobs** on the latest "Deploy to Cloud Run" workflow run in GitHub Actions.
   - **Push a new commit** to `main` (including an empty commit if needed).
4. Watch the workflow until all steps succeed:
   - Build genai bundle
   - Authenticate to Google Cloud
   - Set up gcloud
   - Build and push image
   - Deploy to Cloud Run

Current production URL (update after deploy if the URL changes):

```text
https://claros-505797934944.us-central1.run.app
```

## How to verify production

After a successful deploy, check the production URL.

### Routes and status codes

| URL | Expected |
|-----|----------|
| `/` | 200, marketing landing page only |
| `/app` | 200, worksheet app |
| `/app?sample=1` | 200, app with sample PDF auto-load |
| `/styles/tokens.css` | 200 |
| `/styles/landing.css` | 200 |
| `/styles/app.css` | 200 |
| `/session-rules.js` | 200 |
| `/test-assignment.pdf` | 200 |

### Landing page (`/`)

Must **not** contain worksheet workspace IDs:

- No `id="uploadZone"`
- No `id="micBtn"`

Should contain landing copy such as "Built for students".

### Worksheet app (`/app`)

Must contain:

- `id="uploadZone"`
- `id="micBtn"`
- `loadSamplePdf` (for `/app?sample=1` deep link)

### Functional checks (optional)

If runtime secrets and GCS IAM are correct:

- Upload a PDF or use "Try sample worksheet": `POST /upload` returns 200.
- Export: `GET /export/{assignment_id}?answers=...` returns a PDF.

If upload fails with GCS errors, fix runtime service account bucket permissions, not the workflow file.

### Quick curl examples

```bash
BASE="https://claros-505797934944.us-central1.run.app"

curl -s -o /dev/null -w "%{http_code}\n" "$BASE/"
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/app"
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/styles/app.css"
```

## Manual deploy script

`deploy.sh` mirrors the same image name, service, region defaults, and runtime env vars for local or manual deploys. It requires `gcloud` authentication on your machine and the same runtime secrets as environment variables.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Workflow fails with 0 jobs | Invalid YAML in `deploy.yml` (fixed in commit `b6b2de7`) |
| `must specify exactly one of workload_identity_provider or credentials_json` | Missing or empty `GCP_WIF_PROVIDER` / `GCP_SERVICE_ACCOUNT` |
| `PROJECT_ID` empty in logs | Missing `GCP_PROJECT_ID` secret |
| Deploy succeeds, upload fails | Runtime SA lacks GCS access on the bucket |
| `/app` returns 404 | Stale image still running; redeploy after secrets are fixed |
| `/` shows upload zone | Stale pre-split build; redeploy latest `main` |

## Related files

- `.github/workflows/deploy.yml` - GitHub Actions deploy workflow
- `Dockerfile` - Container image definition
- `deploy.sh` - Manual deploy helper
- `DEPLOY.md` - General Cloud Run notes
