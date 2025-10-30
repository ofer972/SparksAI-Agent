import sys
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
import requests

import config
from api_client import APIClient
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
    print(f"   Job Types: {', '.join(config.JOB_TYPES)}")
    print(f"   Polling Interval: {config.POLLING_INTERVAL_SECONDS} seconds")
    print("=" * 70)

    client = APIClient()
    cycle_count = 0

    backoff_delay = 2  # seconds
    while True:
        cycle_count += 1
        try:
            try:
                status_code, data = client.get_next_pending_job()
            except requests.exceptions.RequestException as e:
                print(
                    f"🌐 Backend unreachable, retrying in {backoff_delay}s (error: {e.__class__.__name__})"
                )
                time.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 2, config.NETWORK_BACKOFF_CAP_SECONDS)
                continue

            # Reset backoff after a successful call
            backoff_delay = 2
            if status_code == 204 or (status_code == 200 and not data):
                print(f"⏳ No jobs ({datetime.now(timezone.utc).strftime('%H:%M:%S')})")
                time.sleep(config.POLLING_INTERVAL_SECONDS)
                continue
            if status_code != 200:
                print(f"⚠️ Failed to get next job: {status_code} {data}")
                time.sleep(config.POLLING_INTERVAL_SECONDS)
                continue

            # Expect a single job object; backend returns { data: { job: {...} } }
            container = data.get("data") if isinstance(data, dict) else data
            job = (
                container.get("job")
                if isinstance(container, dict) and isinstance(container.get("job"), dict)
                else container
            )
            if not isinstance(job, dict):
                print(f"⚠️ Unexpected next-pending response format: {data}")
                time.sleep(config.POLLING_INTERVAL_SECONDS)
                continue

            job_id = _extract_job_id(job)
            if job_id is None:
                print(f"⚠️ Skipping job with missing/invalid id: {job}")
                time.sleep(config.POLLING_INTERVAL_AFTER_JOB_SECONDS)
                continue
            print(
                f"🎯 job_id={job_id} job_type='{job.get('job_type')}' team_name='{job.get('team_name')}' pi='{job.get('pi')}'"
            )

            claim_body = {
                "status": "claimed",
                "claimed_by": str(job.get("job_type", "Unknown")),
                "claimed_at": _now_iso(),
            }
            sc, resp = client.patch_agent_job(job_id, claim_body)
            if sc != 200:
                print(f"⚠️ Claim failed for job {job_id}: {sc} {resp}")
                time.sleep(config.POLLING_INTERVAL_AFTER_JOB_SECONDS)
                continue

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
                print(
                    f"✅ Job {job_id} {'completed' if success else 'failed'}: {result_text[:120]}"
                )
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


