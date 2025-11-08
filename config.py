import os

# Base backend URL (no auth for now)
BASE_URL: str = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# Job processing configuration (mirror existing logic)
JOB_TYPES = [
    "Daily Agent",
    "Sprint Goal",
    "PI Sync",
    "Team PI Insight",
    "Team Retro Topics",
]

# Polling intervals (defaults match current project behavior)
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

POLLING_INTERVAL_SECONDS: int = _int_env("POLLING_INTERVAL", 10)
POLLING_INTERVAL_AFTER_JOB_SECONDS: int = _int_env("POLLING_INTERVAL_AFTER_JOB", 1)

# Single instance for now; keeping flag in case we expand later
PROCESS_JOBS_CONTINUOUSLY: bool = True

# Network backoff when backend is unreachable
NETWORK_BACKOFF_CAP_SECONDS: int = _int_env("NETWORK_BACKOFF_CAP", 300)


