"""Logging utility for job processing with job ID prefix."""


def log(job_id: int | None, message: str) -> None:
    """
    Print log message with job ID prefix.
    
    Args:
        job_id: Job ID (int) or None if not available
        message: Log message to print
    
    Format:
        - If job_id provided: "Job[123] message"
        - If job_id is None: "Job[?] message"
    """
    prefix = f"Job[{job_id}]" if job_id is not None else "Job[?]"
    print(f"{prefix} {message}")

