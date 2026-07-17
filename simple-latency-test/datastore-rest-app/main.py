import time
from datetime import datetime

# 1. Record the absolute start time of the Python interpreter
app_start_time = time.time()

# Log the absolute first possible instruction timestamp
first_execution_dt = datetime.utcfromtimestamp(app_start_time).isoformat() + "Z"
print(f"Container Python started! First execution datetime: {first_execution_dt}", flush=True)

# Perform all necessary imports using standard library only (no external dependencies)
import json
import os
import urllib.request
import urllib.error

def get_project_id():
    # Detect from environment variables first (Cloud Run sets GOOGLE_CLOUD_PROJECT automatically)
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if project_id:
        return project_id
        
    # Fallback to metadata server if running on GCP
    url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
    req = urllib.request.Request(url)
    req.add_header("Metadata-Flavor", "Google")
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Error fetching project ID from metadata server: {e}", flush=True)
        return None

def get_access_token():
    # Check if a custom token is provided (extremely useful for local development/testing)
    if os.environ.get("DATASTORE_ACCESS_TOKEN"):
        return os.environ.get("DATASTORE_ACCESS_TOKEN")
        
    # Query GCP Metadata Server for the default service account's OAuth2 access token
    url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    req = urllib.request.Request(url)
    req.add_header("Metadata-Flavor", "Google")
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("access_token")
    except Exception as e:
        print(f"Error fetching access token from metadata server: {e}", flush=True)
        return None

# Fetch project ID globally during startup
project_id = get_project_id()

# Record the completion of application initialization
app_init_ready_time = time.time()
app_initialization_ms = round((app_init_ready_time - app_start_time) * 1000, 2)

app_init_ready_dt = datetime.utcfromtimestamp(app_init_ready_time).isoformat() + "Z"
print(f"Container Datastore-REST started! Initialization datetime: {app_init_ready_dt}", flush=True)

print(f"Container Datastore-REST started! Project ID: {project_id}. Initialization completed in {app_initialization_ms} ms.", flush=True)

# Perform a warm-up query to the database during startup for REST app (after initialization logs)
if project_id:
    print("Performing startup database warm-up query via REST...", flush=True)
    try:
        token = get_access_token()
        if token:
            url = f"https://datastore.googleapis.com/v1/projects/{project_id}:lookup"
            payload = {
                "databaseId": "datastore-id1",
                "keys": [
                    {
                        "partitionId": {
                            "projectId": project_id,
                            "databaseId": "datastore-id1"
                        },
                        "path": [
                          {
                            "kind": "LatencyTest",
                            "name": "test-entity"
                          }
                        ]
                    }
                ]
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            req.add_header("x-goog-request-params", f"project_id={project_id}&database_id=datastore-id1")
            
            warmup_start_timestamp = time.time()
            warmup_start_dt = datetime.utcfromtimestamp(warmup_start_timestamp).isoformat() + "Z"
            print(f"Warm-up DB request started! datetime: {warmup_start_dt}", flush=True)
            
            with urllib.request.urlopen(req, timeout=5) as response:
                _ = response.read()
                
                warmup_end_timestamp = time.time()
                warmup_end_dt = datetime.utcfromtimestamp(warmup_end_timestamp).isoformat() + "Z"
                print(f"Warm-up DB request completed! datetime: {warmup_end_dt}", flush=True)
                
                print("Startup database warm-up query via REST completed successfully!", flush=True)
        else:
            print("Startup database warm-up query via REST skipped: No access token.", flush=True)
    except Exception as e:
        print(f"Startup database warm-up query via REST failed: {e}", flush=True)

# WSGI application callable for gunicorn
def app(environ, start_response):
    # 2. Record database request start timestamp
    db_request_start_timestamp = time.time()

    db_request_start_dt = datetime.utcfromtimestamp(db_request_start_timestamp).isoformat() + "Z"
    print(f"DB request started! datetime: {db_request_start_dt}", flush=True)
    
    if not project_id:
        db_request_end_timestamp = time.time()
        status_code = '500 Internal Server Error'
        response_data = {
            "status": "error",
            "message": "GCP Project ID could not be determined. Check environment or metadata server.",
            "metrics": {
                "app_initialization_ms": app_initialization_ms,
                "db_request_start_timestamp": db_request_start_timestamp,
                "db_request_end_timestamp": db_request_end_timestamp,
                "db_request_duration_ms": round((db_request_end_timestamp - db_request_start_timestamp) * 1000, 2)
            }
        }
    else:
        # Get access token dynamically per request (GCP Best Practice for token expiration)
        token = get_access_token()
        
        if not token:
            db_request_end_timestamp = time.time()
            status_code = '401 Unauthorized'
            response_data = {
                "status": "error",
                "message": "OAuth2 Access Token could not be retrieved from Metadata Server.",
                "metrics": {
                    "app_initialization_ms": app_initialization_ms,
                    "db_request_start_timestamp": db_request_start_timestamp,
                    "db_request_end_timestamp": db_request_end_timestamp,
                    "db_request_duration_ms": round((db_request_end_timestamp - db_request_start_timestamp) * 1000, 2)
                }
            }
        else:
            url = f"https://datastore.googleapis.com/v1/projects/{project_id}:lookup"
            
            # Construct JSON request body for Datastore lookup API
            payload = {
                "databaseId": "datastore-id1",
                "keys": [
                    {
                        "partitionId": {
                            "projectId": project_id,
                            "databaseId": "datastore-id1"
                        },
                        "path": [
                          {
                            "kind": "LatencyTest",
                            "name": "test-entity"
                          }
                        ]
                    }
                ]
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            req.add_header("x-goog-request-params", f"project_id={project_id}&database_id=datastore-id1")
            
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    db_request_end_timestamp = time.time()
                    
                    found = res_body.get("found", [])
                    if found:
                        entity = found[0].get("entity", {})
                        properties = entity.get("properties", {})
                        
                        message = properties.get("message", {}).get("stringValue", "No message property found")
                        payload_data = properties.get("payload", {}).get("stringValue", "No payload property found")
                        
                        status_code = '200 OK'
                        response_data = {
                            "status": "success",
                            "message": message,
                            "payload": payload_data,
                            "metrics": {
                                "app_initialization_ms": app_initialization_ms,
                                "db_request_start_timestamp": db_request_start_timestamp,
                                "db_request_end_timestamp": db_request_end_timestamp,
                                "db_request_duration_ms": round((db_request_end_timestamp - db_request_start_timestamp) * 1000, 2)
                            }
                        }
                    else:
                        status_code = '404 Not Found'
                        response_data = {
                            "status": "error",
                            "message": "Entity 'LatencyTest/test-entity' not found. Please run the population script first.",
                            "metrics": {
                                "app_initialization_ms": app_initialization_ms,
                                "db_request_start_timestamp": db_request_start_timestamp,
                                "db_request_end_timestamp": db_request_end_timestamp,
                                "db_request_duration_ms": round((db_request_end_timestamp - db_request_start_timestamp) * 1000, 2)
                            }
                        }
            except Exception as e:
                db_request_end_timestamp = time.time()
                status_code = '500 Internal Server Error'
                err_msg = str(e)
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        err_msg += f" - Response: {e.read().decode('utf-8')}"
                    except Exception:
                        pass
                
                response_data = {
                    "status": "error",
                    "message": f"REST API error: {err_msg}",
                    "metrics": {
                        "app_initialization_ms": app_initialization_ms,
                        "db_request_start_timestamp": db_request_start_timestamp,
                        "db_request_end_timestamp": db_request_end_timestamp,
                        "db_request_duration_ms": round((db_request_end_timestamp - db_request_start_timestamp) * 1000, 2)
                    }
                }

    db_request_end_dt = datetime.utcfromtimestamp(db_request_end_timestamp).isoformat() + "Z"
    print(f"DB request completed! datetime: {db_request_end_dt}", flush=True)

    body = json.dumps(response_data).encode('utf-8')
    
    response_headers = [
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(body)))
    ]
    start_response(status_code, response_headers)
    return [body]

# Optional local run without gunicorn if executed directly
if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting local WSGI server on port {port}...", flush=True)
    server = make_server('0.0.0.0', port, app)
    server.serve_forever()
