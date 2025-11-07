from typing import Any, Dict, Tuple

import config
import job_daily_agent
import job_sprint_goal
import job_pi_sync
import job_team_pi_insight
import job_team_retrospective_preparation


def route_and_process(job: Dict[str, Any]) -> Tuple[bool, str]:
    job_type = str(job.get("job_type", ""))
    if job_type == "Daily Agent":
        return job_daily_agent.process(job)
    if job_type == "Sprint Goal":
        return job_sprint_goal.process(job)
    if job_type == "PI Sync":
        return job_pi_sync.process(job)
    if job_type == "Team PI Insight":
        return job_team_pi_insight.process(job)
    if job_type == "Team Retrospective Preparation":
        return job_team_retrospective_preparation.process(job)
    return False, f"Unknown job type: {job_type}"


