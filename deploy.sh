#!/bin/bash
set -e

# -------------------------------------------------------------------------
# Deploy script for GCP Cloud Run Datastore Latency Test applications
# -------------------------------------------------------------------------

# 1. Detect active gcloud project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
  echo "Error: No active gcloud project configured."
  echo "Please set one with: gcloud config set project [PROJECT_ID]"
  exit 1
fi

echo "========================================================================="
echo "GCP PROJECT ID: $PROJECT_ID"
echo "========================================================================="

# 2. Grant datastore.user role to the Default Compute Service Account
echo "Fetching project number..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null || true)

if [ -n "$PROJECT_NUMBER" ]; then
  SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  echo "Default Compute Service Account: $SERVICE_ACCOUNT"
  echo "Adding Datastore User role to the service account..."
  
  # Try to add role. If IAM permissions are lacking, warn but don't fail deploy.
  if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$SERVICE_ACCOUNT" \
      --role="roles/datastore.user" \
      --quiet >/dev/null 2>&1; then
    echo "SUCCESS: 'roles/datastore.user' granted to $SERVICE_ACCOUNT."
  else
    echo "WARNING: Could not automatically grant 'roles/datastore.user' to $SERVICE_ACCOUNT."
    echo "If your deploy fails with permission errors, please ensure this service account has Datastore permissions."
  fi
else
  echo "WARNING: Could not fetch project number. Skipping automatic IAM policy binding."
fi

REGION="southamerica-east1"

echo "========================================================================="
echo "DEPLOYING: datastore-lib-service"
echo "========================================================================="
gcloud run deploy datastore-lib-service \
  --source=./simple-latency-test/datastore-lib-app \
  --region="$REGION" \
  --allow-unauthenticated \
  --quiet

echo "========================================================================="
echo "DEPLOYING: datastore-rest-service"
echo "========================================================================="
gcloud run deploy datastore-rest-service \
  --source=./simple-latency-test/datastore-rest-app \
  --region="$REGION" \
  --allow-unauthenticated \
  --quiet

echo "========================================================================="
echo "DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "========================================================================="

# Fetch URLs
echo "Checking service URLs..."
LIB_URL=$(gcloud run services describe datastore-lib-service --region="$REGION" --format="value(status.url)" 2>/dev/null || echo "Unknown")
REST_URL=$(gcloud run services describe datastore-rest-service --region="$REGION" --format="value(status.url)" 2>/dev/null || echo "Unknown")

echo "Library Service URL: $LIB_URL"
echo "REST API Service URL: $REST_URL"
echo ""
echo "To run the latency comparison:"
echo "1. Run './populate_datastore.sh' to insert the test data."
echo "2. Perform requests to compare cold-start and warm-start latencies:"
echo "   curl $LIB_URL"
echo "   curl $REST_URL"
echo "========================================================================="
