#!/bin/bash

# Configuration
PROJECT_ID="gemini-integration-452515"
SERVICE_NAME="qa-testing-agent"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Starting redeployment for ${SERVICE_NAME}..."

# 1. Build Frontend
echo "📦 Building frontend..."
cd frontend
pnpm install
pnpm build
cd ..

# 2. Build and Push Docker Image (uses the Dockerfile at repo root)
echo "📤 Pushing to Container Registry..."
gcloud builds submit --tag ${IMAGE_NAME} --project ${PROJECT_ID}

# 3. Deploy to Cloud Run
echo "🌍 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \\
  --image ${IMAGE_NAME} \\
  --platform managed \\
  --region ${REGION} \\
  --project ${PROJECT_ID} \\
  --allow-unauthenticated \\
  --memory 2Gi \\
  --cpu 1 \\
  --timeout 3000

echo "✅ Redeployment complete! Service URL: https://qa-testing-agent-1026977097516.us-central1.run.app/"
