#!/usr/bin/env python3
import sys
import os

# Install google-cloud-datastore if not already installed locally
try:
    from google.cloud import datastore
except ImportError:
    print("Installing required google-cloud-datastore library locally...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "google-cloud-datastore==2.23.0"])
    from google.cloud import datastore

def main():
    # Initialize the Datastore client pointing to datastore-id1 database
    # It automatically uses active gcloud/ADC credentials on your machine
    try:
        client = datastore.Client(database="datastore-id1")
    except Exception as e:
        print(f"Error initializing Datastore Client: {e}")
        print("Please ensure you are authenticated in gcloud: 'gcloud auth application-default login'")
        sys.exit(1)

    project_id = client.project
    print(f"Using GCP Project: {project_id}")
    print("Populating Datastore entity (Kind: LatencyTest, ID: test-entity) in database 'datastore-id1'...")

    # Define key and entity
    key = client.key("LatencyTest", "test-entity")
    entity = datastore.Entity(key=key)
    entity.update({
        "message": "Hello from Datastore! Latency test successful.",
        "payload": "Some dummy content to simulate real data transfer and parse. Let us verify performance."
    })

    # Save to Datastore
    try:
        client.put(entity)
        print("SUCCESS: Entity 'LatencyTest/test-entity' upserted successfully in database 'datastore-id1'!")
    except Exception as e:
        print(f"ERROR: Failed to populate Datastore. Details: {e}")
        print("Check if the database 'datastore-id1' has been created in Firestore/Datastore mode.")
        sys.exit(1)

if __name__ == "__main__":
    main()
