#!/usr/bin/env bash
set -euo pipefail

# ---- Config (edit these or provide via env) ----
PROJECT_ID="${PROJECT_ID:-<YOUR_GCP_PROJECT_ID>}"
REGION="${REGION:-<YOUR_REGION>}"             # e.g. us-central1
SERVICE_NAME="${SERVICE_NAME:-claros}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

GEMINI_API_KEY="${GEMINI_API_KEY:-<your-gemini-api-key>}"
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-<your-gcs-bucket>}"
GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID}}"
# -----------------------------------------------+

echo "Building genai bundle..."
npm install
npm run build:genai

echo "Building and pushing image: ${IMAGE}"
gcloud builds submit --tag "${IMAGE}"

echo "Deploying to Cloud Run: ${SERVICE_NAME}"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars \
    GEMINI_API_KEY="${GEMINI_API_KEY}",\
GCS_BUCKET_NAME="${GCS_BUCKET_NAME}",\
GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}"

echo "Deployment complete."

