#!/usr/bin/env python3
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# -------------------------------------------------------------------------
# Configurations
# -------------------------------------------------------------------------
PROJECT_ID = "crun-datastore-latency"
REGION = "southamerica-east1"
SERVICES = [
    "datastore-lib-service",
    "datastore-rest-service",
    "datastore-lib-updated-service"
]
TEST_DURATION_SECONDS = 120  # 2 minutes
CONCURRENCY_PER_SERVICE = 10  # 10 parallel requests per service to force scaling to 5 instances (max-instances)

def get_service_url(service_name):
    cmd = [
        "gcloud", "run", "services", "describe", service_name,
        f"--region={REGION}",
        f"--project={PROJECT_ID}",
        "--format=value(status.url)"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        print(f"Error fetching URL for service {service_name}: {e}", file=sys.stderr)
        return None

def send_request(url):
    start_time = time.time()
    try:
        # Standard urllib request with a short timeout
        req = urllib.request.Request(url, headers={"User-Agent": "Stress-Tester/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            _ = response.read()
            latency = time.time() - start_time
            return True, latency
    except Exception:
        latency = time.time() - start_time
        return False, latency

def stress_service_worker(url, stats_dict, stop_time):
    # Continuously sends requests until the stop_time is reached
    while time.time() < stop_time:
        success, latency = send_request(url)
        if success:
            stats_dict["success"] += 1
            stats_dict["latencies"].append(latency)
        else:
            stats_dict["failed"] += 1

def main():
    print("=" * 80)
    print("                 CLOUD RUN SERVICE STRESS TESTER")
    print("=" * 80)
    print(f"Project ID: {PROJECT_ID}")
    print(f"Region:     {REGION}")
    print(f"Duration:   {TEST_DURATION_SECONDS} seconds (2 minutes)")
    print(f"Threads:    {CONCURRENCY_PER_SERVICE} per service (Total {CONCURRENCY_PER_SERVICE * len(SERVICES)} threads)")
    print("=" * 80)
    
    # 1. Fetch service URLs dynamically
    print("\n[1/3] Fetching service URLs...")
    urls = {}
    for s in SERVICES:
        url = get_service_url(s)
        if url:
            urls[s] = url
            print(f"  • {s}: {url}")
        else:
            print(f"  ❌ Could not resolve URL for {s}. Exiting.", file=sys.stderr)
            sys.exit(1)
            
    # 2. Setup stats collector
    stats = {
        s: {"success": 0, "failed": 0, "latencies": []}
        for s in SERVICES
    }
    
    start_time = time.time()
    stop_time = start_time + TEST_DURATION_SECONDS
    
    print("\n[2/3] Starting stress test. Press Ctrl+C to stop early...")
    
    # Total threads = concurrency * number of services
    total_threads = CONCURRENCY_PER_SERVICE * len(SERVICES)
    
    # 3. Launch threads
    with ThreadPoolExecutor(max_workers=total_threads) as executor:
        futures = []
        for service_name, url in urls.items():
            for _ in range(CONCURRENCY_PER_SERVICE):
                f = executor.submit(stress_service_worker, url, stats[service_name], stop_time)
                futures.append(f)
                
        # Monitor progress in the main thread
        try:
            while time.time() < stop_time:
                elapsed = time.time() - start_time
                remaining = max(0.0, TEST_DURATION_SECONDS - elapsed)
                
                # Print live status summary
                print(
                    f"\r⏳ Elapsed: {elapsed:3.1f}s | Remaining: {remaining:3.1f}s | "
                    f"Lib App: {stats['datastore-lib-service']['success']} OK, {stats['datastore-lib-service']['failed']} ERR | "
                    f"REST App: {stats['datastore-rest-service']['success']} OK, {stats['datastore-rest-service']['failed']} ERR | "
                    f"Updated Lib App: {stats['datastore-lib-updated-service']['success']} OK, {stats['datastore-lib-updated-service']['failed']} ERR",
                    end="",
                    flush=True
                )
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️ Stress test interrupted by user! Stopping workers...")
            # Let the loop end, workers will exit as they check time.time() < stop_time
            
    # Wait for all futures to wind down
    print("\n\n[3/3] Analysis completed. Calculating results...")
    
    # 4. Display Results
    print("\n" + "=" * 80)
    print("                           STRESS TEST RESULTS")
    print("=" * 80)
    
    for s in SERVICES:
        s_stats = stats[s]
        total = s_stats["success"] + s_stats["failed"]
        success_rate = (s_stats["success"] / total * 100) if total > 0 else 0.0
        
        latencies = s_stats["latencies"]
        avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
        min_latency = min(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0
        
        print(f"\n🔹 Service: {s}")
        print("-" * 80)
        print(f"  • Total Requests sent: {total}")
        print(f"  • Successful (200 OK): {s_stats['success']} ({success_rate:.2f}%)")
        print(f"  • Failed Requests:     {s_stats['failed']}")
        if latencies:
            print(f"  • Min Latency:         {min_latency:.4f}s")
            print(f"  • Max Latency:         {max_latency:.4f}s")
            print(f"  • Average Latency:     {avg_latency:.4f}s")
        else:
            print("  • No latency metrics collected (0 successful requests).")
            
    print("\n" + "=" * 80)
    print("💡 SUCCESS: All three services were bombarded! Check your Cloud Run consoles")
    print("   to see them scale up to 5 instances in real-time.")
    print("=" * 80)

if __name__ == "__main__":
    main()
