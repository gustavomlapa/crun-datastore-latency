#!/usr/bin/env python3
import subprocess
import json
import sys
from datetime import datetime

# -------------------------------------------------------------------------
# Configurations
# -------------------------------------------------------------------------
PROJECT_ID = "crun-datastore-latency"
SERVICES = {
    "datastore-lib-service": {
        "init_pattern": "Container Datastore-Lib started! Initialization datetime",
        "label": "Library Service (v2.23.0)"
    },
    "datastore-rest-service": {
        "init_pattern": "Container Datastore-REST started! Initialization datetime",
        "label": "REST API Service"
    },
    "datastore-lib-updated-service": {
        "init_pattern": "Container Datastore-Lib-Updated started! Initialization datetime",
        "label": "Updated Library Service (v2.25.0)"
    }
}

def fetch_logs():
    # Build a unified, highly optimized filter query to fetch everything in 1 call
    service_filters = " OR ".join([f'resource.labels.service_name="{s}"' for s in SERVICES])
    init_patterns = " OR ".join([f'textPayload:"{s["init_pattern"]}"' for s in SERVICES.values()])
    
    query = (
        f'resource.type="cloud_run_revision" '
        f'AND ({service_filters}) '
        f'AND (textPayload:"Starting new instance" OR {init_patterns})'
    )
    
    cmd = [
        "gcloud", "logging", "read", query,
        f"--project={PROJECT_ID}",
        "--format=json",
        "--limit=300"
    ]
    
    print(f"Connecting to Google Cloud (Project: {PROJECT_ID})...")
    print("Fetching instance startup logs (this may take a few seconds)...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\nError executing gcloud command: {e}", file=sys.stderr)
        if e.stderr:
            print(f"Details: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def process_logs(logs):
    # Group structure: service_name -> instance_id -> { "platform_start": timestamp, "app_init": timestamp }
    grouped_data = {s: {} for s in SERVICES}
    
    for entry in logs:
        resource_labels = entry.get("resource", {}).get("labels", {})
        service_name = resource_labels.get("service_name")
        
        if service_name not in SERVICES:
            continue
            
        instance_id = entry.get("labels", {}).get("instanceId")
        if not instance_id:
            continue
            
        payload = entry.get("textPayload", "")
        timestamp = entry.get("timestamp")
        
        # Ensure the instance dict exists for this service
        if instance_id not in grouped_data[service_name]:
            grouped_data[service_name][instance_id] = {}
            
        # Classify the log entry
        if "Starting new instance" in payload:
            grouped_data[service_name][instance_id]["platform_start"] = timestamp
        else:
            # Check if this payload contains any of our expected initialization patterns
            for s_name, config in SERVICES.items():
                if config["init_pattern"] in payload:
                    grouped_data[service_name][instance_id]["app_init"] = timestamp
                    break

    return grouped_data

def display_results(grouped_data):
    print("\n" + "=" * 80)
    print("                CLOUD RUN COLD-START LATENCY ANALYSIS")
    print("=" * 80)
    
    for service_name, instances in grouped_data.items():
        label = SERVICES[service_name]["label"]
        print(f"\n🔹 SERVICE: {service_name} ({label})")
        print("-" * 80)
        
        valid_durations = []
        individual_results = []
        
        for inst_id, times in instances.items():
            if "platform_start" in times and "app_init" in times:
                try:
                    t1 = datetime.fromisoformat(times["platform_start"].replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(times["app_init"].replace("Z", "+00:00"))
                    duration = (t2 - t1).total_seconds()
                    
                    valid_durations.append(duration)
                    individual_results.append({
                        "instance_id": inst_id,
                        "platform_start": times["platform_start"],
                        "app_init": times["app_init"],
                        "duration": duration
                    })
                except Exception as e:
                    # Ignore parsing issues with malformed timestamps
                    continue
        
        if not valid_durations:
            print("  No completed cold-start instances found in the fetched log window.")
            continue
            
        # Display Stats
        avg_dur = sum(valid_durations) / len(valid_durations)
        min_dur = min(valid_durations)
        max_dur = max(valid_durations)
        
        print(f"  Summary Statistics ({len(valid_durations)} instances analysed):")
        print(f"    • Minimum platform-to-app delay: {min_dur:.4f} seconds")
        print(f"    • Maximum platform-to-app delay: {max_dur:.4f} seconds")
        print(f"    • Average platform-to-app delay: {avg_dur:.4f} seconds")
        print("\n  Individual Instance Breakdown:")
        
        # Sort individual results by platform start time descending
        individual_results.sort(key=lambda x: x["platform_start"], reverse=True)
        for idx, res in enumerate(individual_results, 1):
            short_id = res["instance_id"][:12]
            print(f"    [{idx}] Instance: {short_id}...")
            print(f"        Platform Start: {res['platform_start']}")
            print(f"        Container Init: {res['app_init']}")
            print(f"        Time Delay:     {res['duration']:.4f} seconds")
            
    print("\n" + "=" * 80)

def main():
    logs = fetch_logs()
    if not logs:
        print("No log entries found matching the query criteria.")
        return
        
    grouped_data = process_logs(logs)
    display_results(grouped_data)

if __name__ == "__main__":
    main()
