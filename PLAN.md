# PLAN

Checklist for implementing the GCP Datastore Latency Test applications (Library vs REST) and corresponding scripts.

- [x] Create `populate_datastore.sh` in the project root to insert the test entity into GCP Datastore.
- [x] Create the `datastore-lib-app` directory and define `requirements.txt` (with gunicorn & google-cloud-datastore).
- [x] Create `Dockerfile` in `datastore-lib-app`.
- [x] Create `main.py` in `datastore-lib-app` implementing WSGI server and GCP Datastore SDK lookup.
- [x] Create the `datastore-rest-app` directory and define `requirements.txt` (with only gunicorn).
- [x] Create `Dockerfile` in `datastore-rest-app`.
- [x] Create `main.py` in `datastore-rest-app` implementing WSGI server and manual Datastore REST lookup using Python's standard `urllib`.
- [x] Create `deploy.sh` in the project root to deploy both services to GCP Cloud Run via `gcloud run deploy --source`.
- [x] Verify everything by executing the scripts and testing endpoints.
