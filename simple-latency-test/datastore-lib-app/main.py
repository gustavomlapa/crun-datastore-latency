import time

# 1. Record the absolute start time of the Python interpreter
app_start_time = time.time()

# Perform all necessary imports and library loading
from google.cloud import datastore
import json
import os

# Initialize the Datastore client globally (GCP best practice for Cloud Run connection pooling)
client = datastore.Client(database="datastore-id1")

# Record the completion of application initialization
app_init_ready_time = time.time()
app_initialization_ms = round((app_init_ready_time - app_start_time) * 1000, 2)

print(f"Container Datastore-Lib started! Initialization completed in {app_initialization_ms} ms.", flush=True)

# WSGI application callable for gunicorn
def app(environ, start_response):
    # Retrieve the entity key
    key = client.key("LatencyTest", "test-entity")
    
    # 2. Record database request start timestamp
    db_request_start_timestamp = time.time()
    
    try:
        entity = client.get(key)
        db_request_end_timestamp = time.time()
        
        if entity:
            message = entity.get("message", "No message property found")
            payload = entity.get("payload", "No payload property found")
            status_code = '200 OK'
            response_data = {
                "status": "success",
                "message": message,
                "payload": payload,
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
        response_data = {
            "status": "error",
            "message": f"An error occurred: {str(e)}",
            "metrics": {
                "app_initialization_ms": app_initialization_ms,
                "db_request_start_timestamp": db_request_start_timestamp,
                "db_request_end_timestamp": db_request_end_timestamp,
                "db_request_duration_ms": round((db_request_end_timestamp - db_request_start_timestamp) * 1000, 2)
            }
        }

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
