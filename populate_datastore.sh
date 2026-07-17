#!/usr/bin/env bash
# -------------------------------------------------------------------------
# Script wrapper to populate GCP Datastore via local Python SDK
# -------------------------------------------------------------------------
set -e

# Run the python script which targets datastore-id1 database and handles credentials automatically
python3 "$(dirname "$0")/populate_datastore.py"
