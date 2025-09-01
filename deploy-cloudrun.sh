#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy-cloudrun.sh <gcp-project-id> <service-name> <region>
# Example: ./deploy-cloudrun.sh my-proj memegen us-central1

PROJECT_ID=${1:-playground-292010}
SERVICE_NAME=${2:-ineedameme}
REGION=${3:-europe-west1}

if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 <gcp-project-id> <service-name> <region>" >&2
  exit 1
fi

gcloud config set project "$PROJECT_ID"

# Build container with Cloud Build (no local Docker required)
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" .

# Deploy to Cloud Run
CMD=(gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  --region "$REGION" \
  --platform managed \
  --port 8080 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --memory 1Gi \
  --timeout 300)

"${CMD[@]}"

echo "Set OPENROUTER_API_KEY as a Cloud Run secret or env var:"
echo "  gcloud run services update ${SERVICE_NAME} --region ${REGION} --set-env-vars OPENROUTER_API_KEY=YOUR_KEY"

# Quick & dirty: apply all vars from local .env to Cloud Run (ignores comments and blank lines)
# Note: this is brittle if values contain commas/newlines. Use env.yaml for production.
if [[ -f .env ]]; then
  echo "Applying environment variables from .env to Cloud Run (quick & dirty)..."
  ENV_STR=$(grep -v '^#' .env | grep -v '^\s*$' | paste -sd, -)
  if [[ -n "${ENV_STR}" ]]; then
    gcloud run services update "${SERVICE_NAME}" --region "${REGION}" --set-env-vars "${ENV_STR}"
  else
    echo ".env has no non-comment entries; skipping env update."
  fi
fi
