from typing import Any, Dict, Tuple

import config
import job_daily_progress
import job_sprint_goal
import job_pi_sync
import job_team_pi_insight
import job_team_retro_topics
import job_pi_dependencies
import job_pi_planning_gaps
import job_group_sprint_flow
import job_group_sprint_predictability
import job_group_sprint_dependency
from utils_llm_processing_and_extraction import JSONExtractionError


def route_and_process(job: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        job_type = str(job.get("job_type", ""))
        if job_type.strip() == "Test":
            return True, ""
        if job_type == "daily-progress":
            return job_daily_progress.process(job)
        if job_type == "sprint-goal":
            return job_sprint_goal.process(job)
        if job_type == "pi-sync":
            return job_pi_sync.process(job)
        if job_type == "team-pi-insight":
            return job_team_pi_insight.process(job)
        if job_type == "team-retro-topics":
            return job_team_retro_topics.process(job)
        if job_type == "pi-dependencies":
            return job_pi_dependencies.process(job)
        if job_type == "pi-planning-gaps":
            return job_pi_planning_gaps.process(job)
        if job_type == "group-sprint-flow":
            return job_group_sprint_flow.process(job)
        if job_type == "group-sprint-predictability":
            return job_group_sprint_predictability.process(job)
        if job_type == "group-sprint-dependency":
            return job_group_sprint_dependency.process(job)
        return False, f"Unknown job type: {job_type}"
    except JSONExtractionError as e:
        return False, str(e)


