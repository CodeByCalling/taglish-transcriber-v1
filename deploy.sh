#!/bin/bash

# Deploy to Google Cloud Run
# Region: us-central1 (adjust if needed)
# Allow unauthenticated: Yes, because our app has internal password protection.

# Load .env variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

echo "🚀 Deploying Taglish Transcriber to Cloud Run..."
echo " > Using Project ID from serviceAccountKey..."

gcloud run deploy taglish-transcriber-v1 \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars APP_PASSWORD=$APP_PASSWORD \
  --set-env-vars OPENAI_API_KEY=$OPENAI_API_KEY \
  --memory 4Gi \
  --cpu 2 \
  --timeout 5m \
  --no-cpu-throttling
