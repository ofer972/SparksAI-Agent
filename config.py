import os

# Base backend URL (no auth for now)
BASE_URL: str = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# Job processing configuration - uses insight_id values
JOB_TYPES = [
    "daily-progress",
    "sprint-goal",
    "pi-sync",
    "team-pi-insight",
    "team-retro-topics",
    "pi-dependencies",
    "pi-planning-gaps",
    "group-sprint-flow",
    "group-sprint-predictability",
    "group-sprint-dependency",
]

# Polling intervals (defaults match current project behavior)
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

POLLING_INTERVAL_SECONDS: int = _int_env("POLLING_INTERVAL", 20)
POLLING_INTERVAL_AFTER_JOB_SECONDS: int = _int_env("POLLING_INTERVAL_AFTER_JOB", 2)

# Single instance for now; keeping flag in case we expand later
PROCESS_JOBS_CONTINUOUSLY: bool = True

# Network backoff when backend is unreachable
NETWORK_BACKOFF_CAP_SECONDS: int = _int_env("NETWORK_BACKOFF_CAP", 300)

# API timeout configuration
API_TIMEOUT_SECONDS: int = _int_env("API_TIMEOUT", 60)
LLM_TIMEOUT_SECONDS: int = _int_env("LLM_TIMEOUT", 120)

# Audit service configuration
AUDIT_SERVICE_URL: str = os.getenv("AUDIT_SERVICE_URL", "")


