from typing import Any, Dict, Tuple

import config
import job_daily_progress
import job_sprint_goal
import job_pi_sync
import job_team_pi_insight
import job_team_retro_topics


def route_and_process(job: Dict[str, Any]) -> Tuple[bool, str]:
    job_type = str(job.get("job_type", ""))
    if job_type == "Daily Progress":
        return job_daily_progress.process(job)
    if job_type == "Sprint Goal":
        return job_sprint_goal.process(job)
    if job_type == "PI Sync":
        return job_pi_sync.process(job)
    if job_type == "Team PI Insight":
        return job_team_pi_insight.process(job)
    # Backward compatibility: support old job type name "Team Retrospective Preparation"
    if job_type == "Team Retrospective Preparation":
        return job_team_retro_topics.process(job)
    if job_type == "Team Retro Topics":
        return job_team_retro_topics.process(job)
    return False, f"Unknown job type: {job_type}"


