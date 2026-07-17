#!/bin/bash
set -e

# -------------------------------------------------------------------------
# Script to populate GCP Datastore with a test entity for latency comparison
# -------------------------------------------------------------------------

# 1. Get current active gcloud project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ]; then
  echo "Error: No active gcloud project configured."
  echo "Please set one with 'gcloud config set project [PROJECT_ID]'"
  exit 1
fi

echo "Using GCP Project: $PROJECT_ID"
echo "Populating Datastore entity (Kind: LatencyTest, Name: test-entity)..."

# Get temporary OAuth2 access token for authentication
ACCESS_TOKEN=$(gcloud auth print-access-token)

# UTC formatted ISO 8601 timestamp for updated_at field
UTC_NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Send POST request to Datastore commit endpoint (NON_TRANSACTIONAL upsert)
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "NON_TRANSACTIONAL",
    "mutations": [
      {
        "upsert": {
          "key": {
            "partitionId": {
              "projectId": "'"$PROJECT_ID"'",
              "databaseId": "datastore-id1"
            },
            "path": [
              {
                "kind": "LatencyTest",
                "name": "test-entity"
              }
            ]
          },
          "properties": {
            "message": {
              "stringValue": "Hello from Datastore! Latency test successful."
            },
            "payload": {
              "stringValue": "Some dummy content to simulate real data transfer and parse. Let us verify performance."
            },
            "updated_at": {
              "timestampValue": "'"$UTC_NOW"'"
            }
          }
        }
      }
    ]
  }' \
  "https://datastore.googleapis.com/v1/projects/${PROJECT_ID}/databases/datastore-id1:commit")

HTTP_BODY=$(echo "$RESPONSE" | sed '$d')
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)

if [ "$HTTP_STATUS" -eq 200 ]; then
  echo "SUCCESS: Entity 'LatencyTest/test-entity' upserted successfully!"
  echo "Response payload:"
  echo "$HTTP_BODY"
else
  echo "ERROR: Failed to populate Datastore. HTTP Status: $HTTP_STATUS"
  echo "Response:"
  echo "$HTTP_BODY"
  exit 1
fi
