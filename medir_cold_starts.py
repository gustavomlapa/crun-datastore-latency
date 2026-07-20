#!/usr/bin/env python3
import subprocess
import json
import sys
import argparse
from datetime import datetime, timedelta

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

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze Cloud Run cold-start latencies with precise instance pairing.")
    parser.add_argument(
        "--minutes", "-m",
        type=int,
        default=15,
        help="Fetch logs from the last N minutes (default: 15). Use longer windows to see past runs, or shorter during active tests."
    )
    return parser.parse_args()

def fetch_logs(minutes_ago):
    # Build a unified, highly optimized filter query to fetch everything in 1 call
    service_filters = " OR ".join([f'resource.labels.service_name="{s}"' for s in SERVICES])
    init_patterns = " OR ".join([f'textPayload:"{s["init_pattern"]}"' for s in SERVICES.values()])
    
    # Restrict to a tight time window (e.g., last 15 minutes) to avoid stale logs during stress tests
    time_threshold = (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat() + "Z"
    
    query = (
        f'resource.type="cloud_run_revision" '
        f'AND ({service_filters}) '
        f'AND (textPayload:"Starting new instance" OR {init_patterns}) '
        f'AND timestamp >= "{time_threshold}"'
    )
    
    cmd = [
        "gcloud", "logging", "read", query,
        f"--project={PROJECT_ID}",
        "--format=json",
        "--limit=500"
    ]
    
    print(f"Connecting to Google Cloud (Project: {PROJECT_ID})...")
    print(f"Fetching logs from the last {minutes_ago} minutes to isolate current run...")
    
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
    
    # Sort logs chronologically (oldest first) to ensure clean mapping if duplicate logs exist
    sorted_logs = sorted(logs, key=lambda x: x.get("timestamp", ""))
    
    for entry in sorted_logs:
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
            
        # Classify the log entry with strict, isolated service boundaries
        if "Starting new instance" in payload:
            grouped_data[service_name][instance_id]["platform_start"] = timestamp
        elif SERVICES[service_name]["init_pattern"] in payload:
            grouped_data[service_name][instance_id]["app_init"] = timestamp

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
                    
                    # Sanity check: App initialization cannot physically occur before Platform Start.
                    # This filters out any orphaned logs or clock desynchronizations.
                    if duration < 0:
                        continue
                        
                    valid_durations.append(duration)
                    individual_results.append({
                        "instance_id": inst_id,
                        "platform_start": times["platform_start"],
                        "app_init": times["app_init"],
                        "duration": duration
                    })
                except Exception:
                    continue
        
        if not valid_durations:
            print("  No completed cold-start instances found in this time window.")
            continue
            
        # Display Stats
        avg_dur = sum(valid_durations) / len(valid_durations)
        min_dur = min(valid_durations)
        max_dur = max(valid_durations)
        
        print(f"  Summary Statistics ({len(valid_durations)} instances paired and analyzed):")
        print(f"    • Minimum platform-to-app delay: {min_dur:.4f} seconds")
        print(f"    • Maximum platform-to-app delay: {max_dur:.4f} seconds")
        print(f"    • Average platform-to-app delay: {avg_dur:.4f} seconds")
        print("\n  Pairing Details (Chronological - newest first):")
        
        # Sort individual results by platform start time descending
        individual_results.sort(key=lambda x: x["platform_start"], reverse=True)
        for idx, res in enumerate(individual_results, 1):
            short_id = res["instance_id"][:12]
            print(f"    [{idx}] Instance ID: {short_id}...")
            print(f"        • Platform Start: {res['platform_start']}")
            print(f"        • Container Init: {res['app_init']}")
            print(f"        • Startup Delay:  {res['duration']:.4f} seconds")
            
    print("\n" + "=" * 80)
    print("💡 TIP: Grouping is strictly bound by instanceId. Cross-service logs and")
    print("   concurrent startups cannot interfere or confuse the measurements.")
    print("=" * 80)

def main():
    args = parse_args()
    logs = fetch_logs(args.minutes)
    if not logs:
        print("No log entries found matching the query criteria.")
        return
        
    grouped_data = process_logs(logs)
    display_results(grouped_data)

if __name__ == "__main__":
    main()
