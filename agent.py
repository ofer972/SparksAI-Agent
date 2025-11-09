import sys
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
import requests

import config
from api_client import APIClient, wait_for_backend
from job_router import route_and_process


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _select_pending_supported(jobs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    for job in jobs or []:
        status = str(job.get("status", "")).lower()
        job_type = str(job.get("job_type", ""))
        if status == "pending" and job_type in config.JOB_TYPES:
            return job
    return None


def _extract_job_id(job: Dict[str, Any]) -> int | None:
    candidate = job.get("job_id", job.get("id"))
    if candidate is None:
        return None
    try:
        return int(candidate)
    except Exception:
        return None


def run_agent() -> None:
    print("=" * 70)
    print("🚀 Starting SparksAI-Agent")
    print(f"   Backend: {config.BASE_URL}")
    print(f"   Job-Types: {', '.join(config.JOB_TYPES)}")
    print(f"   Polling Interval: {config.POLLING_INTERVAL_SECONDS} seconds")
    print("=" * 70)

    client = APIClient()
    
    # Check backend health at startup
    status_code, _ = wait_for_backend(
        lambda: client.check_health(),
        operation_name="health check",
    )
    if status_code == 200:
        print("✅ Backend health OK")
    
    cycle_count = 0
    no_jobs_count = 0  # Counter for consecutive "no jobs" messages
    no_jobs_timings = []  # Track timings for "no jobs" cases

    while True:
        cycle_count += 1
        try:
            # Health check before claiming next job (commented out - may need to use)
            # health_start_time = time.time()
            # health_status, _ = wait_for_backend(
            #     lambda: client.check_health(),
            #     operation_name="health check",
            # )
            # health_elapsed_time = time.time() - health_start_time
            # print(f"🏥 Health check → {health_status} (round trip: {health_elapsed_time*1000:.1f}ms)")
            
            # Time the claim_next_pending_job call
            start_time = time.time()
            status_code, data = wait_for_backend(
                lambda: client.claim_next_pending_job(),
                operation_name="claim next pending job",
            )
            elapsed_time = time.time() - start_time
            
            if status_code == 204 or (status_code == 200 and not data):
                no_jobs_count += 1
                no_jobs_timings.append(elapsed_time)
                # Only print every 10th "no jobs" message with average timing
                if no_jobs_count % 10 == 0:
                    if len(no_jobs_timings) > 0:
                        avg_time = sum(no_jobs_timings) / len(no_jobs_timings)
                        total_time = sum(no_jobs_timings)
                        print(f"⏳ No jobs (checked 10 times, avg response time: {avg_time*1000:.1f}ms, total: {total_time*1000:.1f}ms, count: {len(no_jobs_timings)}, {datetime.now(timezone.utc).strftime('%H:%M:%S')})")
                    else:
                        print(f"⏳ No jobs (checked 10 times, {datetime.now(timezone.utc).strftime('%H:%M:%S')})")
                    no_jobs_timings = []  # Reset after logging
                time.sleep(config.POLLING_INTERVAL_SECONDS)
                continue
            
            # Reset counter when job is found
            no_jobs_count = 0
            no_jobs_timings = []  # Reset timings when job is found
            if status_code != 200:
                print(f"⚠️ Failed to claim next job: {status_code} {data} (response time: {elapsed_time*1000:.1f}ms)")
                time.sleep(config.POLLING_INTERVAL_SECONDS)
                continue

            # Job found successfully - print message with timing
            print(f"✅ Job found (response time: {elapsed_time*1000:.1f}ms)")

            # Expect a single job object; backend returns { data: { job: {...} } }
            container = data.get("data") if isinstance(data, dict) else data
            job = (
                container.get("job")
                if isinstance(container, dict) and isinstance(container.get("job"), dict)
                else container
            )
            if not isinstance(job, dict):
                print(f"⚠️ Unexpected next-pending response format: {data} (response time: {elapsed_time*1000:.1f}ms)")
                time.sleep(config.POLLING_INTERVAL_SECONDS)
                continue

            job_id = _extract_job_id(job)
            if job_id is None:
                print(f"⚠️ Skipping job with missing/invalid id: {job} (response time: {elapsed_time*1000:.1f}ms)")
                time.sleep(config.POLLING_INTERVAL_AFTER_JOB_SECONDS)
                continue
            print(
                f"🎯 job_id={job_id} job_type='{job.get('job_type')}' team_name='{job.get('team_name')}' pi='{job.get('pi')}'"
            )

            # Job is already claimed by backend - proceed directly to processing
            input_text = (
                f"SparksAI-Agent collected basic job context at {datetime.now(timezone.utc).isoformat()}"
            )
            sc, _ = client.patch_agent_job(job_id, {"input_sent": input_text})
            if sc != 200:
                print(f"⚠️ Failed updating input_sent for {job_id}")

            success, result_text = route_and_process(job)

            final_body = {
                "status": "completed" if success else "error",
                "result": result_text if success else None,
                "error": None if success else (result_text or "Unknown error"),
            }
            sc, resp = client.patch_agent_job(job_id, final_body)
            if sc == 200:
                # Build concise summary with Team and Timestamp
                first_line = (result_text.split('\n')[0].strip() if result_text else "Unknown")[:100]
                team = job.get("team_name", "Unknown")
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                summary = f"{first_line} - Team: {team} - Timestamp: {timestamp}"
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                print(f"✅ Job {job_id} {'completed' if success else 'failed'}: {summary}")
            else:
                print(f"⚠️ Final update failed for job {job_id}: {sc} {resp}")

            time.sleep(config.POLLING_INTERVAL_AFTER_JOB_SECONDS)

        except KeyboardInterrupt:
            print("\n⚠️ Interrupted - shutting down")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Unexpected error in agent loop: {e}")
            time.sleep(30)


if __name__ == "__main__":
    run_agent()


